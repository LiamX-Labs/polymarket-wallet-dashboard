import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs';
import { DashboardDB } from './db';
import { SyncService } from './sync';
import { createWalletsRouter } from './routes/wallets';

dotenv.config();

const PORT = process.env.PORT || 3001;
const TRACKER_DB_PATH = process.env.TRACKER_DB_PATH || path.join(__dirname, '../../data/tracker.sqlite3');
const DASHBOARD_DB_PATH = process.env.DASHBOARD_DB_PATH || path.join(__dirname, '../../data/dashboard.db');
const SYNC_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

const app = express();

// Middleware - Configure CORS to allow frontend access
const corsOptions = {
  origin: process.env.CORS_ORIGIN || '*',
  credentials: true,
  optionsSuccessStatus: 200
};
app.use(cors(corsOptions));
app.use(express.json());

// Ensure dashboard database directory exists
const dashboardDbDir = path.dirname(DASHBOARD_DB_PATH);
if (!fs.existsSync(dashboardDbDir)) {
  fs.mkdirSync(dashboardDbDir, { recursive: true });
  console.log(`[SERVER] Created dashboard database directory: ${dashboardDbDir}`);
}

// Wait for tracker database to be created by the tracker
async function waitForTrackerDb(maxWaitSeconds = 60) {
  const startTime = Date.now();
  while (!fs.existsSync(TRACKER_DB_PATH)) {
    const elapsed = (Date.now() - startTime) / 1000;
    if (elapsed > maxWaitSeconds) {
      console.warn(`[SERVER] Tracker database not found after ${maxWaitSeconds}s: ${TRACKER_DB_PATH}`);
      console.warn(`[SERVER] Server will start anyway. Sync will fail until tracker creates the database.`);
      break;
    }
    console.log(`[SERVER] Waiting for tracker database... (${elapsed.toFixed(0)}s)`);
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  if (fs.existsSync(TRACKER_DB_PATH)) {
    console.log(`[SERVER] Tracker database found: ${TRACKER_DB_PATH}`);
  }
}

// Initialize databases
// NOTE: Tracker DB is opened READ-ONLY, Dashboard DB is a SEPARATE database
const dashboardDb = new DashboardDB(DASHBOARD_DB_PATH);
let syncService: SyncService | null = null;

// Routes
app.use('/api/wallets', createWalletsRouter(dashboardDb));

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'Polymarket Wallet Dashboard API',
    version: '1.0.0',
    status: 'running',
    endpoints: [
      'GET /api/health',
      'GET /api/wallets',
      'GET /api/wallets/:address',
      'POST /api/sync'
    ]
  });
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    success: true,
    status: 'ok',
    timestamp: new Date().toISOString(),
  });
});

// Debug endpoint to check sync status
app.get('/api/debug', (req, res) => {
  const trackerDbExists = fs.existsSync(TRACKER_DB_PATH);
  const dashboardDbExists = fs.existsSync(DASHBOARD_DB_PATH);

  res.json({
    success: true,
    trackerDbPath: TRACKER_DB_PATH,
    trackerDbExists,
    dashboardDbPath: DASHBOARD_DB_PATH,
    dashboardDbExists,
    syncServiceInitialized: syncService !== null,
    timestamp: new Date().toISOString(),
  });
});

// Manual sync endpoint
app.post('/api/sync', (req, res) => {
  if (!syncService) {
    res.status(503).json({
      success: false,
      error: 'Sync service not initialized - tracker database not available yet',
    });
    return;
  }
  try {
    syncService.sync();
    res.json({
      success: true,
      message: 'Sync completed successfully',
    });
  } catch (error) {
    console.error('Manual sync failed:', error);
    res.status(500).json({
      success: false,
      error: 'Sync failed',
    });
  }
});

// Catch-all 404 handler - MUST come after all valid routes
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: `Route ${req.method} ${req.originalUrl} not found`,
    availableEndpoints: [
      'GET /',
      'GET /api/health',
      'GET /api/wallets',
      'GET /api/wallets/:address',
      'POST /api/sync'
    ]
  });
});

// Auto-sync every 5 minutes
let syncInterval: NodeJS.Timeout;

async function startAutoSync() {
  if (!syncService) {
    console.warn('[SERVER] Cannot start auto-sync: sync service not initialized');
    return;
  }

  console.log(`[SERVER] Starting auto-sync every ${SYNC_INTERVAL_MS / 1000}s`);

  // Initial sync
  try {
    syncService.sync();
  } catch (error) {
    console.error('[SERVER] Initial sync failed:', error);
  }

  // Schedule periodic sync
  syncInterval = setInterval(() => {
    if (syncService) {
      try {
        syncService.sync();
      } catch (error) {
        console.error('[SERVER] Scheduled sync failed:', error);
      }
    }
  }, SYNC_INTERVAL_MS);
}

// Start server
app.listen(PORT, async () => {
  console.log(`[SERVER] Running on http://localhost:${PORT}`);
  console.log(`[SERVER] ========================================`);
  console.log(`[SERVER] Tracker DB (READ-ONLY):   ${TRACKER_DB_PATH}`);
  console.log(`[SERVER] Dashboard DB (SEPARATE):  ${DASHBOARD_DB_PATH}`);
  console.log(`[SERVER] ========================================`);
  console.log(`[SERVER] NOTE: Dashboard uses its own separate database.`);
  console.log(`[SERVER]       Tracker database is never modified (read-only).`);
  console.log(`[SERVER] ========================================`);

  // Wait for tracker database then initialize sync service
  await waitForTrackerDb();

  if (fs.existsSync(TRACKER_DB_PATH)) {
    try {
      syncService = new SyncService(TRACKER_DB_PATH, DASHBOARD_DB_PATH);
      await startAutoSync();
    } catch (error) {
      console.error('[SERVER] Failed to initialize sync service:', error);
      console.warn('[SERVER] Server will continue running but sync is disabled');
    }
  } else {
    console.warn('[SERVER] Tracker database not found. Sync is disabled.');
    console.warn('[SERVER] The tracker needs to run and create the database first.');
  }
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n[SERVER] Shutting down gracefully...');
  if (syncInterval) {
    clearInterval(syncInterval);
  }
  dashboardDb.close();
  if (syncService) {
    syncService.close();
  }
  process.exit(0);
});

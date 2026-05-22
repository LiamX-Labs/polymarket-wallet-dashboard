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

// Middleware
app.use(cors());
app.use(express.json());

// Ensure dashboard database directory exists
const dashboardDbDir = path.dirname(DASHBOARD_DB_PATH);
if (!fs.existsSync(dashboardDbDir)) {
  fs.mkdirSync(dashboardDbDir, { recursive: true });
  console.log(`[SERVER] Created dashboard database directory: ${dashboardDbDir}`);
}

// Initialize databases
// NOTE: Tracker DB is opened READ-ONLY, Dashboard DB is a SEPARATE database
const dashboardDb = new DashboardDB(DASHBOARD_DB_PATH);
const syncService = new SyncService(TRACKER_DB_PATH, DASHBOARD_DB_PATH);

// Routes
app.use('/api/wallets', createWalletsRouter(dashboardDb));

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    success: true,
    status: 'ok',
    timestamp: new Date().toISOString(),
  });
});

// Manual sync endpoint
app.post('/api/sync', (req, res) => {
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

// Auto-sync every 5 minutes
let syncInterval: NodeJS.Timeout;

function startAutoSync() {
  console.log(`[SERVER] Starting auto-sync every ${SYNC_INTERVAL_MS / 1000}s`);

  // Initial sync
  try {
    syncService.sync();
  } catch (error) {
    console.error('[SERVER] Initial sync failed:', error);
  }

  // Schedule periodic sync
  syncInterval = setInterval(() => {
    try {
      syncService.sync();
    } catch (error) {
      console.error('[SERVER] Scheduled sync failed:', error);
    }
  }, SYNC_INTERVAL_MS);
}

// Start server
app.listen(PORT, () => {
  console.log(`[SERVER] Running on http://localhost:${PORT}`);
  console.log(`[SERVER] ========================================`);
  console.log(`[SERVER] Tracker DB (READ-ONLY):   ${TRACKER_DB_PATH}`);
  console.log(`[SERVER] Dashboard DB (SEPARATE):  ${DASHBOARD_DB_PATH}`);
  console.log(`[SERVER] ========================================`);
  console.log(`[SERVER] NOTE: Dashboard uses its own separate database.`);
  console.log(`[SERVER]       Tracker database is never modified (read-only).`);
  console.log(`[SERVER] ========================================`);

  startAutoSync();
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n[SERVER] Shutting down gracefully...');
  clearInterval(syncInterval);
  dashboardDb.close();
  syncService.close();
  process.exit(0);
});

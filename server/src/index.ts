import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs';
import { usePostgres, isVercelEnabled, getSyncIntervalMs, isLowMemoryMode, isRender } from './config';
import { createDashboardDB, createSyncService } from './db-factory';
import { DashboardDatabase, SyncServiceLike } from './db-interface';
import { createWalletsRouter } from './routes/wallets';

dotenv.config();

const PORT = process.env.PORT || 3001;
const TRACKER_DB_PATH = process.env.TRACKER_DB_PATH || path.join(__dirname, '../../data/tracker.sqlite3');
const DASHBOARD_DB_PATH = process.env.DASHBOARD_DB_PATH || path.join(__dirname, '../../data/dashboard.db');
const SYNC_INTERVAL_MS = getSyncIntervalMs();

const app = express();

const corsOptions = {
  origin: process.env.CORS_ORIGIN || '*',
  credentials: true,
  optionsSuccessStatus: 200,
};
app.use(cors(corsOptions));
app.use(express.json());

const clientDistPath = path.join(__dirname, '../../client/dist');
if (!isRender() && fs.existsSync(clientDistPath)) {
  app.use(express.static(clientDistPath));
  console.log(`[SERVER] Serving static files from ${clientDistPath}`);
}

let dashboardDb: DashboardDatabase | null = null;
let syncService: SyncServiceLike | null = null;
const initPromise = initializeApp();
let lastSyncTime: Date | null = null;
let lastSyncWalletCount = 0;
let syncInterval: NodeJS.Timeout | undefined;

async function initializeApp(): Promise<void> {
  if (dashboardDb) return;

  if (!usePostgres()) {
    const dashboardDbDir = path.dirname(DASHBOARD_DB_PATH);
    if (!fs.existsSync(dashboardDbDir)) {
      fs.mkdirSync(dashboardDbDir, { recursive: true });
      console.log(`[SERVER] Created dashboard database directory: ${dashboardDbDir}`);
    }
  }

  dashboardDb = await createDashboardDB(DASHBOARD_DB_PATH);

  if (!usePostgres()) {
    await waitForTrackerDb();
  }

  syncService = await createSyncService(TRACKER_DB_PATH, dashboardDb, DASHBOARD_DB_PATH);

  if (syncService) {
    console.log(`[SERVER] Sync service initialized (${usePostgres() ? 'PostgreSQL' : 'SQLite'})`);
    if (!isVercelEnabled()) {
      await startAutoSync();
    }
  } else {
    console.warn('[SERVER] Sync service not available');
  }

  app.use('/api/wallets', createWalletsRouter(dashboardDb));

  app.use((req, res) => {
    res.status(404).json({
      success: false,
      error: `Route ${req.method} ${req.originalUrl} not found`,
      availableEndpoints: [
        'GET /',
        'GET /api/health',
        'GET /api/wallets',
        'GET /api/wallets/:address',
        'POST /api/sync',
      ],
    });
  });
}

async function waitForTrackerDb(maxWaitSeconds = 60): Promise<void> {
  const startTime = Date.now();
  while (!fs.existsSync(TRACKER_DB_PATH)) {
    const elapsed = (Date.now() - startTime) / 1000;
    if (elapsed > maxWaitSeconds) {
      console.warn(`[SERVER] Tracker database not found after ${maxWaitSeconds}s: ${TRACKER_DB_PATH}`);
      break;
    }
    console.log(`[SERVER] Waiting for tracker database... (${elapsed.toFixed(0)}s)`);
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  if (fs.existsSync(TRACKER_DB_PATH)) {
    console.log(`[SERVER] Tracker database found: ${TRACKER_DB_PATH}`);
  }
}

app.use(async (req, res, next) => {
  try {
    await initPromise;
    next();
  } catch (error) {
    console.error('[SERVER] Initialization failed:', error);
    res.status(503).json({ success: false, error: 'Server is initializing' });
  }
});

if (!isRender()) {
  app.get(/^\/(?!api\/)/, (req, res) => {
    const indexPath = path.join(__dirname, '../../client/dist/index.html');
    if (fs.existsSync(indexPath)) {
      res.sendFile(indexPath);
    } else {
      res.status(404).json({
        success: false,
        error: 'Client build not found. Please run `cd client && npm run build`',
      });
    }
  });
}

app.get('/', (req, res) => {
  res.json({
    name: 'Polymarket Wallet Dashboard API',
    version: '1.0.0',
    status: 'running',
    database: usePostgres() ? 'postgresql' : 'sqlite',
    endpoints: [
      'GET /api/health',
      'GET /api/wallets',
      'GET /api/wallets/:address',
      'POST /api/sync',
    ],
  });
});

app.get('/api/health', (req, res) => {
  res.json({
    success: true,
    status: 'ok',
    database: usePostgres() ? 'postgresql' : 'sqlite',
    timestamp: new Date().toISOString(),
  });
});

app.get('/api/debug', async (req, res) => {
  const trackerDbExists = usePostgres() ? true : fs.existsSync(TRACKER_DB_PATH);
  const dashboardDbExists = usePostgres() ? true : fs.existsSync(DASHBOARD_DB_PATH);
  const currentWalletCount = dashboardDb
    ? await dashboardDb.getWalletCount()
    : 0;

  let trackerLatestUpdate: number | null = null;
  let needsSync = false;
  if (syncService) {
    trackerLatestUpdate = await syncService.getLatestTrackerUpdate();
    needsSync = await syncService.needsSync();
  }

  res.json({
    success: true,
    database: usePostgres() ? 'postgresql' : 'sqlite',
    trackerDbPath: usePostgres() ? 'postgresql:wallet_dashboard_summary' : TRACKER_DB_PATH,
    trackerDbExists,
    dashboardDbPath: usePostgres() ? 'postgresql:wallet_dashboard_stats' : DASHBOARD_DB_PATH,
    dashboardDbExists,
    syncServiceInitialized: syncService !== null,
    lastSyncTime: lastSyncTime?.toISOString() || 'Never',
    lastSyncWalletCount,
    currentWalletCount,
    syncStrategy: 'Smart polling - only syncs when tracker has new data',
    syncCheckIntervalMs: SYNC_INTERVAL_MS,
    trackerLatestUpdate: trackerLatestUpdate
      ? new Date(trackerLatestUpdate * 1000).toISOString()
      : null,
    needsSync,
    timestamp: new Date().toISOString(),
  });
});

app.post('/api/sync', async (req, res) => {
  if (!syncService) {
    res.status(503).json({
      success: false,
      error: 'Sync service not initialized',
    });
    return;
  }
  try {
    await syncService.sync();
    lastSyncTime = new Date();
    lastSyncWalletCount = dashboardDb
      ? await dashboardDb.getWalletCount()
      : 0;
    res.json({
      success: true,
      message: 'Sync completed successfully',
      walletCount: lastSyncWalletCount,
    });
  } catch (error) {
    console.error('Manual sync failed:', error);
    res.status(500).json({
      success: false,
      error: 'Sync failed',
    });
  }
});

async function startAutoSync(): Promise<void> {
  if (!syncService) return;

  console.log(`[SERVER] Starting auto-sync every ${SYNC_INTERVAL_MS / 1000}s`);

  let initialSyncAttempts = 0;
  const maxInitialAttempts = 3;

  async function attemptInitialSync(): Promise<void> {
    try {
      initialSyncAttempts++;
      console.log(`[SERVER] Attempting initial sync (attempt ${initialSyncAttempts}/${maxInitialAttempts})...`);

      if (syncService) {
        await syncService.sync();
        lastSyncTime = new Date();

        const walletCount = dashboardDb
          ? await dashboardDb.getWalletCount()
          : 0;
        lastSyncWalletCount = walletCount;

        if (walletCount === 0 && initialSyncAttempts < maxInitialAttempts) {
          console.warn('[SERVER] Initial sync returned 0 wallets. Retrying in 30s...');
          setTimeout(attemptInitialSync, 30000);
        } else if (walletCount === 0) {
          console.warn(`[SERVER] Initial sync still returns 0 wallets after ${maxInitialAttempts} attempts.`);
        } else {
          console.log(`[SERVER] Initial sync successful! Dashboard has ${walletCount} wallets.`);
        }
      }
    } catch (error) {
      console.error('[SERVER] Initial sync failed:', error);
      if (initialSyncAttempts < maxInitialAttempts) {
        setTimeout(attemptInitialSync, 30000);
      }
    }
  }

  await attemptInitialSync();

  syncInterval = setInterval(async () => {
    if (!syncService) return;
    try {
      if (await syncService.needsSync()) {
        console.log('[SERVER] Tracker has new data. Running sync...');
        await syncService.sync();
        lastSyncTime = new Date();
        lastSyncWalletCount = dashboardDb
          ? await dashboardDb.getWalletCount()
          : 0;
        if (!isLowMemoryMode()) {
          console.log(`[SERVER] Sync complete. Dashboard has ${lastSyncWalletCount} wallets.`);
        }
      }
    } catch (error) {
      console.error('[SERVER] Scheduled sync check failed:', error);
    }
  }, SYNC_INTERVAL_MS);
}

export default app;

if (!isVercelEnabled()) {
  initPromise.then(() => {
    app.listen(PORT, () => {
      console.log(`[SERVER] Running on http://localhost:${PORT}`);
      console.log(`[SERVER] Database mode: ${usePostgres() ? 'PostgreSQL' : 'SQLite'}`);
      if (!usePostgres()) {
        console.log(`[SERVER] Tracker DB (READ-ONLY):   ${TRACKER_DB_PATH}`);
        console.log(`[SERVER] Dashboard DB (SEPARATE):  ${DASHBOARD_DB_PATH}`);
      }
    });
  }).catch((error) => {
    console.error('[SERVER] Failed to start:', error);
    process.exit(1);
  });
} else {
  console.log('[SERVER] Running on Vercel - Serverless Mode');
}

process.on('SIGINT', async () => {
  console.log('\n[SERVER] Shutting down gracefully...');
  if (syncInterval) clearInterval(syncInterval);
  if (dashboardDb) await dashboardDb.close();
  if (syncService) await syncService.close();
  process.exit(0);
});

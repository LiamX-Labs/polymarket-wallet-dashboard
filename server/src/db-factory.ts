import { usePostgres } from './config';
import { DashboardDatabase, SyncServiceLike } from './db-interface';

export async function createDashboardDB(dbPath?: string): Promise<DashboardDatabase> {
  if (usePostgres()) {
    const { PostgresDashboardDB } = await import('./postgres-db.js');
    const db = new PostgresDashboardDB();
    await db.initSchema();
    return db;
  }

  const { SqliteDashboardDB } = await import('./db.js');
  const path = dbPath || process.env.DASHBOARD_DB_PATH || '../data/dashboard.db';
  return new SqliteDashboardDB(path);
}

export async function createSyncService(
  trackerDbPath: string,
  dashboardDb: DashboardDatabase,
  dashboardDbPath?: string
): Promise<SyncServiceLike | null> {
  if (usePostgres()) {
    const { PostgresSyncService } = await import('./postgres-sync.js');
    return new PostgresSyncService(dashboardDb);
  }

  const fs = await import('fs');
  if (!fs.existsSync(trackerDbPath)) {
    return null;
  }

  const { SqliteSyncService } = await import('./sync.js');
  const path = dashboardDbPath || process.env.DASHBOARD_DB_PATH || '../data/dashboard.db';
  return new SqliteSyncService(trackerDbPath, path);
}

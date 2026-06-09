/** Vercel deployment is kept in-repo but disabled by default. */
export function isVercelEnabled(): boolean {
  return process.env.VERCEL === '1' && process.env.VERCEL_ENABLED !== 'false';
}

/** Returns the Postgres connection URL from Vercel/Render Postgres or Neon. */
export function getPostgresUrl(): string | undefined {
  if (process.env.USE_POSTGRES === 'false') {
    return undefined;
  }
  return (
    process.env.POSTGRES_URL ||
    process.env.DATABASE_URL ||
    process.env.POSTGRES_URL_NON_POOLING
  );
}

/** True when the server should use PostgreSQL instead of local SQLite files. */
export function usePostgres(): boolean {
  return !!getPostgresUrl();
}

export function isRender(): boolean {
  return !!process.env.RENDER;
}

export function isLowMemoryMode(): boolean {
  return process.env.LOW_MEMORY_MODE === 'true' || isRender();
}

/** Sync polling interval — longer on Render to reduce memory churn. */
export function getSyncIntervalMs(): number {
  const configured = parseInt(process.env.SYNC_INTERVAL_MS || '', 10);
  if (!Number.isNaN(configured) && configured > 0) {
    return configured;
  }
  return isLowMemoryMode() ? 120_000 : 30_000;
}

/** @deprecated Use isVercelEnabled() */
export function isVercel(): boolean {
  return isVercelEnabled();
}

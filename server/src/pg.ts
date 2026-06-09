import { neon } from '@neondatabase/serverless';
import { getPostgresUrl } from './config';

let sqlInstance: ReturnType<typeof neon> | null = null;

export function getSql() {
  if (!sqlInstance) {
    const url = getPostgresUrl();
    if (!url) {
      throw new Error('POSTGRES_URL or DATABASE_URL must be set for PostgreSQL mode');
    }
    sqlInstance = neon(url);
  }
  return sqlInstance;
}

/** Normalize Neon query results to a typed row array. */
export function asRows<T>(result: unknown): T[] {
  if (Array.isArray(result)) {
    return result as T[];
  }
  if (result && typeof result === 'object' && 'rows' in result) {
    return (result as { rows: T[] }).rows;
  }
  return [];
}

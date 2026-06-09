import { asRows, getSql } from './pg';
import { SyncServiceLike } from './db-interface';
import { DashboardDatabase } from './db-interface';
import { WalletStats } from './types';

function strOrNull(value: unknown): string | null {
  if (value == null) return null;
  return String(value);
}

function numOrNull(value: unknown): number | null {
  if (value == null) return null;
  return Number(value);
}

function summaryToStats(wallet: string, summary: Record<string, unknown>): WalletStats {
  return {
    wallet,
    profit_24h: Number(summary.profit_24h) || 0,
    recent_trade_market: strOrNull(summary.recent_trade_market),
    recent_trade_side: strOrNull(summary.recent_trade_side),
    recent_trade_timestamp: numOrNull(summary.recent_trade_timestamp),
    recent_trade_pnl: numOrNull(summary.recent_trade_pnl),
    avg_time_between_positions: Number(summary.avg_time_between_positions) || 0,
    last_position_timestamp: numOrNull(summary.last_position_timestamp),
    win_rate: Number(summary.win_rate) || 0,
    total_trades: Number(summary.total_trades) || 0,
    avg_trades_per_day: Number(summary.avg_trades_per_day) || 0,
    avg_hold_time_seconds: Number(summary.avg_hold_time_seconds) || 0,
    avg_win: Number(summary.avg_win) || 0,
    avg_loss: Number(summary.avg_loss) || 0,
    best_trade_amount: Number(summary.best_trade_amount) || 0,
    best_trade_time_ago: numOrNull(summary.best_trade_time_ago),
    worst_trade_amount: Number(summary.worst_trade_amount) || 0,
    worst_trade_time_ago: numOrNull(summary.worst_trade_time_ago),
    best_perf_amount: Number(summary.best_perf_amount) || 0,
    best_perf_count: Number(summary.best_perf_count) || 0,
    best_perf_time_ago: null,
    worst_perf_amount: Number(summary.worst_perf_amount) || 0,
    worst_perf_count: Number(summary.worst_perf_count) || 0,
    worst_perf_time_ago: null,
    num_wins: Number(summary.num_wins) || 0,
    num_losses: Number(summary.num_losses) || 0,
    avg_trade_size: Number(summary.avg_trade_size) || 0,
    profit_factor: Number(summary.profit_factor) || 0,
    last_updated: Number(summary.last_updated) || Math.floor(Date.now() / 1000),
  };
}

export class PostgresSyncService implements SyncServiceLike {
  private dashboardDb: DashboardDatabase;
  private lastTrackerUpdate = 0;

  constructor(dashboardDb: DashboardDatabase) {
    this.dashboardDb = dashboardDb;
  }

  async getLatestTrackerUpdate(): Promise<number> {
    try {
      const sql = getSql();
      const rows = asRows<{ max_update: number | null }>(await sql`
        SELECT MAX(last_updated) AS max_update FROM wallet_dashboard_summary
      `);
      const value = rows[0]?.max_update;
      return value != null ? Number(value) : 0;
    } catch (error) {
      console.error('[SYNC] Error checking tracker update time:', error);
      return 0;
    }
  }

  async needsSync(): Promise<boolean> {
    const latest = await this.getLatestTrackerUpdate();
    return latest > this.lastTrackerUpdate;
  }

  async sync(): Promise<void> {
    console.log('[SYNC] Starting PostgreSQL wallet stats sync...');
    const startTime = Date.now();
    const sql = getSql();
    const sevenDaysAgo = Math.floor(Date.now() / 1000) - 7 * 24 * 60 * 60;

    let summaries = asRows<Record<string, unknown>>(await sql`
      SELECT * FROM wallet_dashboard_summary
      WHERE last_updated >= ${sevenDaysAgo}
      ORDER BY last_updated DESC
    `);

    if (summaries.length === 0) {
      summaries = asRows<Record<string, unknown>>(await sql`
        SELECT * FROM wallet_dashboard_summary
        ORDER BY last_updated DESC
      `);
    }

    console.log(`[SYNC] Found ${summaries.length} wallets in PostgreSQL summary table`);

    let synced = 0;
    for (const summary of summaries) {
      const wallet = String(summary.wallet ?? '');
      if (!wallet) continue;
      try {
        await this.dashboardDb.upsertWalletStats(summaryToStats(wallet, summary));
        synced++;
      } catch (error) {
        console.error(`[SYNC] Error processing wallet ${wallet}:`, error);
      }
    }

    const duration = Date.now() - startTime;
    console.log(`[SYNC] PostgreSQL sync complete. Synced ${synced}/${summaries.length} wallets in ${duration}ms`);
    this.lastTrackerUpdate = await this.getLatestTrackerUpdate();
  }

  async close(): Promise<void> {
    await this.dashboardDb.close();
  }
}

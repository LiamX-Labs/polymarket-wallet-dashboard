import { asRows, getSql } from './pg';
import { SyncServiceLike } from './db-interface';
import { DashboardDatabase } from './db-interface';
import { WalletStats } from './types';

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
    console.log('[SYNC] Starting PostgreSQL optimized sync (SQL-to-SQL)...');
    const startTime = Date.now();
    const sql = getSql();
    
    // 7-day lookback for active wallets
    const sevenDaysAgo = Math.floor(Date.now() / 1000) - 7 * 24 * 60 * 60;

    try {
      /**
       * PERFORM ATOMIC SYNC VIA SINGLE SQL QUERY
       * This is the most memory-efficient way to sync in PostgreSQL mode.
       * Instead of pulling thousands of records into Node.js memory, we let
       * the database perform the upsert directly between tables.
       */
      await sql`
        INSERT INTO wallet_dashboard_stats (
          wallet, profit_24h, recent_trade_market, recent_trade_side,
          recent_trade_timestamp, recent_trade_pnl, avg_time_between_positions,
          last_position_timestamp, win_rate, total_trades, avg_trades_per_day,
          avg_hold_time_seconds, avg_win, avg_loss, best_trade_amount,
          best_trade_time_ago, worst_trade_amount, worst_trade_time_ago,
          best_perf_amount, best_perf_time_ago, best_perf_count,
          worst_perf_amount, worst_perf_time_ago, worst_perf_count,
          num_wins, num_losses, avg_trade_size, profit_factor, last_updated
        )
        SELECT
          wallet, profit_24h, recent_trade_market, recent_trade_side,
          recent_trade_timestamp, recent_trade_pnl, avg_time_between_positions,
          last_position_timestamp, win_rate, total_trades, avg_trades_per_day,
          avg_hold_time_seconds, avg_win, avg_loss, best_trade_amount,
          best_trade_time_ago, worst_trade_amount, worst_trade_time_ago,
          best_perf_amount, NULL as best_perf_time_ago, best_perf_count,
          worst_perf_amount, NULL as worst_perf_time_ago, worst_perf_count,
          num_wins, num_losses, avg_trade_size, profit_factor, last_updated
        FROM wallet_dashboard_summary
        WHERE last_updated >= ${sevenDaysAgo}
        ON CONFLICT (wallet) DO UPDATE SET
          profit_24h = EXCLUDED.profit_24h,
          recent_trade_market = EXCLUDED.recent_trade_market,
          recent_trade_side = EXCLUDED.recent_trade_side,
          recent_trade_timestamp = EXCLUDED.recent_trade_timestamp,
          recent_trade_pnl = EXCLUDED.recent_trade_pnl,
          avg_time_between_positions = EXCLUDED.avg_time_between_positions,
          last_position_timestamp = EXCLUDED.last_position_timestamp,
          win_rate = EXCLUDED.win_rate,
          total_trades = EXCLUDED.total_trades,
          avg_trades_per_day = EXCLUDED.avg_trades_per_day,
          avg_hold_time_seconds = EXCLUDED.avg_hold_time_seconds,
          avg_win = EXCLUDED.avg_win,
          avg_loss = EXCLUDED.avg_loss,
          best_trade_amount = EXCLUDED.best_trade_amount,
          best_trade_time_ago = EXCLUDED.best_trade_time_ago,
          worst_trade_amount = EXCLUDED.worst_trade_amount,
          worst_trade_time_ago = EXCLUDED.worst_trade_time_ago,
          best_perf_amount = EXCLUDED.best_perf_amount,
          best_perf_count = EXCLUDED.best_perf_count,
          worst_perf_amount = EXCLUDED.worst_perf_amount,
          worst_perf_count = EXCLUDED.worst_perf_count,
          num_wins = EXCLUDED.num_wins,
          num_losses = EXCLUDED.num_losses,
          avg_trade_size = EXCLUDED.avg_trade_size,
          profit_factor = EXCLUDED.profit_factor,
          last_updated = EXCLUDED.last_updated
      `;

      const duration = Date.now() - startTime;
      console.log(`[SYNC] PostgreSQL atomic sync complete in ${duration}ms`);
      this.lastTrackerUpdate = await this.getLatestTrackerUpdate();
    } catch (error) {
      console.error('[SYNC] PostgreSQL atomic sync failed:', error);
      throw error;
    }
  }

  async close(): Promise<void> {
    await this.dashboardDb.close();
  }
}

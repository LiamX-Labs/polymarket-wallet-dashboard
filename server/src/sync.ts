import Database from 'better-sqlite3';
import { SqliteDashboardDB } from './db';
import { SyncServiceLike } from './db-interface';
import { WalletStats } from './types';

export class SqliteSyncService implements SyncServiceLike {
  private trackerDb: Database.Database;
  private dashboardDb: SqliteDashboardDB;
  private lastTrackerUpdate: number = 0;

  constructor(trackerDbPath: string, dashboardDbPath: string) {
    this.trackerDb = new Database(trackerDbPath, { readonly: true });
    this.dashboardDb = new SqliteDashboardDB(dashboardDbPath);
  }

  /**
   * Check if tracker has new data since last sync.
   */
  async getLatestTrackerUpdate(): Promise<number> {
    try {
      const result = this.trackerDb
        .prepare(`SELECT MAX(last_updated) as max_update FROM wallet_dashboard_summary`)
        .get() as { max_update: number | null };
      return result?.max_update || 0;
    } catch (error) {
      console.error('[SYNC] Error checking tracker update time:', error);
      return 0;
    }
  }

  async needsSync(): Promise<boolean> {
    const latest = await this.getLatestTrackerUpdate();
    return latest > this.lastTrackerUpdate;
  }

  /**
   * Sync wallet data from tracker database.
   *
   * Optimized path: reads from wallet_dashboard_summary — a denormalized table
   * written by the Python tracker that already contains all pre-calculated metrics
   * including avg_win, avg_loss, best/worst trade, streak amounts/counts, and
   * avg_trade_size.  The tracker's wallet_profiler.calculate_pnl_metrics() computes
   * all of these correctly; the sync layer's job is simply to transfer them to the
   * dashboard database.
   *
   * Falls back to the legacy multi-query method (wallet_stats_7d) if the summary
   * table is empty.
   */
  async sync(): Promise<void> {
    console.log('[SYNC] Starting wallet stats sync...');
    const startTime = Date.now();

    const sevenDaysAgo = Math.floor(Date.now() / 1000) - 7 * 24 * 60 * 60;
    const oneDayAgo    = Math.floor(Date.now() / 1000) - 24 * 60 * 60;

    // Primary: optimized path from unified summary table
    let wallets = this.trackerDb
      .prepare(
        `SELECT wallet FROM wallet_dashboard_summary
         WHERE last_updated >= ?
         ORDER BY last_updated DESC`
      )
      .all(sevenDaysAgo) as Array<{ wallet: string }>;

    if (wallets.length === 0) {
      wallets = this.trackerDb
        .prepare(`SELECT wallet FROM wallet_dashboard_summary ORDER BY last_updated DESC`)
        .all() as Array<{ wallet: string }>;
    }

    // Fallback to legacy tables if summary is empty
    let usingLegacyMethod = false;
    if (wallets.length === 0) {
      console.log('[SYNC] Unified summary table empty, falling back to legacy method...');
      wallets = this.trackerDb
        .prepare(
          `SELECT DISTINCT wallet FROM wallet_stats_7d WHERE as_of_ts >= ?`
        )
        .all(sevenDaysAgo) as Array<{ wallet: string }>;
      usingLegacyMethod = true;

      if (wallets.length === 0) {
        wallets = this.trackerDb
          .prepare(`SELECT DISTINCT wallet FROM wallet_stats_7d`)
          .all() as Array<{ wallet: string }>;
      }
    }

    console.log(`[SYNC] Found ${wallets.length} wallets (${usingLegacyMethod ? 'LEGACY' : 'OPTIMIZED'} method)`);

    let synced = 0;
    for (const { wallet } of wallets) {
      try {
        const stats = usingLegacyMethod
          ? this.calculateWalletStats(wallet, sevenDaysAgo, oneDayAgo)
          : this.getWalletStatsOptimized(wallet);

        if (stats) {
          await this.dashboardDb.upsertWalletStats(stats);
          synced++;
        } else {
          console.warn(`[SYNC] No stats returned for wallet ${wallet}`);
        }
      } catch (error) {
        console.error(`[SYNC] Error processing wallet ${wallet}:`, error);
        if (error instanceof Error) {
          console.error(`[SYNC] Stack: ${error.stack}`);
        }
      }
    }

    const duration = Date.now() - startTime;
    console.log(
      `[SYNC] ${usingLegacyMethod ? 'LEGACY' : 'OPTIMIZED'} sync complete. ` +
      `Synced ${synced}/${wallets.length} wallets in ${duration}ms`
    );

    this.lastTrackerUpdate = await this.getLatestTrackerUpdate();

    try {
      const verifyCount = await this.dashboardDb.getWalletCount();
      console.log(`[SYNC] Dashboard now contains ${verifyCount} wallets`);
    } catch (error) {
      console.error('[SYNC] Failed to verify dashboard database:', error);
    }
  }

  /**
   * Optimized path: direct pass-through from wallet_dashboard_summary.
   *
   * All metrics are pre-calculated by the Python tracker's
   * wallet_profiler.calculate_pnl_metrics(). We simply map column names.
   */
  private getWalletStatsOptimized(wallet: string): WalletStats | null {
    const summary = this.trackerDb
      .prepare(`SELECT * FROM wallet_dashboard_summary WHERE wallet = ?`)
      .get(wallet) as any;

    if (!summary) return null;

    const stats: WalletStats = {
      wallet,

      // Today / Recent Activity
      profit_24h:                 summary.profit_24h                 || 0,
      recent_trade_market:        summary.recent_trade_market         || null,
      recent_trade_side:          summary.recent_trade_side           || null,
      recent_trade_timestamp:     summary.recent_trade_timestamp      || null,
      recent_trade_pnl:           summary.recent_trade_pnl            || null,
      avg_time_between_positions: summary.avg_time_between_positions  || 0,
      last_position_timestamp:    summary.last_position_timestamp     || null,

      // 7-Day Track Record
      win_rate:              summary.win_rate              || 0,
      total_trades:          summary.total_trades          || 0,
      avg_trades_per_day:    summary.avg_trades_per_day    || 0,
      avg_hold_time_seconds: summary.avg_hold_time_seconds || 0,

      // Performance Metrics — pre-calculated from closed positions by the tracker
      avg_win:              summary.avg_win              || 0,
      avg_loss:             summary.avg_loss             || 0,
      best_trade_amount:    summary.best_trade_amount    || 0,
      best_trade_time_ago:  summary.best_trade_time_ago  || null,
      worst_trade_amount:   summary.worst_trade_amount   || 0,
      worst_trade_time_ago: summary.worst_trade_time_ago || null,

      // Streak Metrics — pre-calculated by tracker's calculate_pnl_metrics()
      best_perf_amount:    summary.best_perf_amount    || 0,
      best_perf_count:     summary.best_perf_count     || 0,
      best_perf_time_ago:  summary.best_perf_time_ago  || null,
      worst_perf_amount:   summary.worst_perf_amount   || 0,
      worst_perf_count:    summary.worst_perf_count    || 0,
      worst_perf_time_ago: summary.worst_perf_time_ago || null,

      num_wins:        summary.num_wins        || 0,
      num_losses:      summary.num_losses      || 0,
      avg_trade_size:  summary.avg_trade_size  || 0,
      profit_factor:   summary.profit_factor   || 0,

      last_updated: summary.last_updated || Math.floor(Date.now() / 1000),
    };

    return stats;
  }

  // ---------------------------------------------------------------------------
  // Legacy fallback (wallet_stats_7d / top_wallet_performance tables).
  // Used only when wallet_dashboard_summary is empty.
  // ---------------------------------------------------------------------------
  private calculateWalletStats(
    wallet: string,
    sevenDaysAgo: number,
    oneDayAgo: number
  ): WalletStats | null {
    const statsRows = this.trackerDb
      .prepare(
        `SELECT * FROM wallet_stats_7d
         WHERE wallet = ?
         ORDER BY as_of_ts DESC`
      )
      .all(wallet) as any[];

    if (statsRows.length === 0) return null;

    const latestStats = statsRows[0];

    const positions = this.trackerDb
      .prepare(
        `SELECT *
         FROM top_wallet_picks
         WHERE wallet = ?
         ORDER BY scan_event_id DESC
         LIMIT 50`
      )
      .all(wallet) as any[];

    const recentTrade = positions.length > 0 ? positions[0] : null;
    const avgTimeBetween = this.calculateAvgTimeBetween(positions);

    // Use top_wallet_performance for accurate P&L metrics when available
    const performanceMetrics = this.trackerDb
      .prepare(
        `SELECT * FROM top_wallet_performance
         WHERE wallet = ?
         ORDER BY id DESC
         LIMIT 1`
      )
      .get(wallet) as any;

    let avgWin = 0, avgLoss = 0, numWins = 0, numLosses = 0;
    let bestTradeAmount = 0, worstTradeAmount = 0;
    let bestPerfAmount = 0, bestPerfCount = 0;
    let worstPerfAmount = 0, worstPerfCount = 0;
    let avgTradeSize = latestStats.avg_trade_size || 0;
    let profitFactor = 0;

    if (performanceMetrics) {
      avgWin           = performanceMetrics.avg_win        || 0;
      avgLoss          = performanceMetrics.avg_loss       || 0;
      numWins          = performanceMetrics.num_wins       || 0;
      numLosses        = performanceMetrics.num_losses     || 0;
      bestTradeAmount  = performanceMetrics.best_trade     || 0;
      worstTradeAmount = performanceMetrics.worst_trade    || 0;
      profitFactor     = performanceMetrics.profit_factor  || 0;
      // Legacy top_wallet_performance has no streak columns — leave as 0
    }

    const stats: WalletStats = {
      wallet,

      profit_24h:                 0,
      recent_trade_market:        recentTrade?.market_title          || null,
      recent_trade_side:          recentTrade?.side                   || null,
      recent_trade_timestamp:     recentTrade?.trigger_ts             || null,
      recent_trade_pnl:           null,
      avg_time_between_positions: avgTimeBetween,
      last_position_timestamp:    recentTrade?.trigger_ts             || null,

      win_rate:              latestStats.win_rate    || 0,
      total_trades:          latestStats.trade_count || 0,
      avg_trades_per_day:    (latestStats.trade_count || 0) / 7,
      avg_hold_time_seconds: this.calculateAvgHoldTime(positions),

      avg_win:              avgWin,
      avg_loss:             avgLoss,
      best_trade_amount:    bestTradeAmount,
      best_trade_time_ago:  null,
      worst_trade_amount:   worstTradeAmount,
      worst_trade_time_ago: null,
      best_perf_amount:     bestPerfAmount,
      best_perf_count:      bestPerfCount,
      best_perf_time_ago:   null,
      worst_perf_amount:    worstPerfAmount,
      worst_perf_count:     worstPerfCount,
      worst_perf_time_ago:  null,
      num_wins:             numWins,
      num_losses:           numLosses,
      avg_trade_size:       avgTradeSize,
      profit_factor:        profitFactor,

      last_updated: Math.floor(Date.now() / 1000),
    };

    return stats;
  }

  private calculateAvgTimeBetween(positions: any[]): number {
    if (positions.length < 2) return 0;
    const timestamps = positions.map((p) => p.trigger_ts).sort((a, b) => a - b);
    const intervals: number[] = [];
    for (let i = 1; i < timestamps.length; i++) {
      intervals.push(timestamps[i] - timestamps[i - 1]);
    }
    return intervals.length > 0
      ? Math.floor(intervals.reduce((sum, val) => sum + val, 0) / intervals.length)
      : 0;
  }

  private calculateAvgHoldTime(positions: any[]): number {
    if (positions.length < 2) return 300;
    const timestamps = positions
      .map((p) => p.trigger_ts)
      .filter((ts) => ts)
      .sort((a, b) => a - b);
    if (timestamps.length < 2) return 300;
    const intervals: number[] = [];
    for (let i = 1; i < timestamps.length; i++) {
      intervals.push(timestamps[i] - timestamps[i - 1]);
    }
    return intervals.length > 0
      ? Math.floor(intervals.reduce((sum, val) => sum + val, 0) / intervals.length)
      : 300;
  }

  async close(): Promise<void> {
    this.trackerDb.close();
    await this.dashboardDb.close();
  }
}

/** @deprecated Use SqliteSyncService or createSyncService() */
export const SyncService = SqliteSyncService;

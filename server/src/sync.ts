import Database from 'better-sqlite3';
import { DashboardDB } from './db';
import { WalletStats } from './types';

export class SyncService {
  private trackerDb: Database.Database;
  private dashboardDb: DashboardDB;
  private lastTrackerUpdate: number = 0;

  constructor(trackerDbPath: string, dashboardDbPath: string) {
    this.trackerDb = new Database(trackerDbPath, { readonly: true });
    this.dashboardDb = new DashboardDB(dashboardDbPath);
  }

  /**
   * Check if tracker has new data since last sync
   * Returns the latest update timestamp from tracker, or 0 if no data
   */
  getLatestTrackerUpdate(): number {
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

  /**
   * Check if sync is needed (tracker has new data)
   */
  needsSync(): boolean {
    const latestUpdate = this.getLatestTrackerUpdate();
    return latestUpdate > this.lastTrackerUpdate;
  }

  /**
   * Sync wallet data from tracker database using optimized unified summary table
   * Performs single-query retrieval per wallet from wallet_dashboard_summary
   * Falls back to legacy multi-query method if unified table is empty
   */
  sync(): void {
    console.log('[SYNC] Starting optimized wallet stats sync...');
    const startTime = Date.now();

    const sevenDaysAgo = Math.floor(Date.now() / 1000) - 7 * 24 * 60 * 60;
    const oneDayAgo = Math.floor(Date.now() / 1000) - 24 * 60 * 60;

    // Try to get wallets from unified dashboard summary table (optimized path)
    let wallets = this.trackerDb
      .prepare(
        `SELECT wallet FROM wallet_dashboard_summary
         WHERE last_updated >= ?
         ORDER BY last_updated DESC`
      )
      .all(sevenDaysAgo) as Array<{ wallet: string }>;

    // Fallback: If no recent data, try all wallets from summary table
    if (wallets.length === 0) {
      wallets = this.trackerDb
        .prepare(`SELECT wallet FROM wallet_dashboard_summary ORDER BY last_updated DESC`)
        .all() as Array<{ wallet: string }>;
    }

    // Fallback to legacy method if unified table is empty
    let usingLegacyMethod = false;
    if (wallets.length === 0) {
      console.log('[SYNC] Unified summary table empty, falling back to legacy multi-query method...');
      wallets = this.trackerDb
        .prepare(
          `SELECT DISTINCT wallet
           FROM wallet_stats_7d
           WHERE as_of_ts >= ?`
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
          this.dashboardDb.upsertWalletStats(stats);
          synced++;
        } else {
          console.warn(`[SYNC] No stats returned for wallet ${wallet}`);
        }
      } catch (error) {
        console.error(`[SYNC] Error processing wallet ${wallet}:`, error);
        if (error instanceof Error) {
          console.error(`[SYNC] Error details: ${error.message}`);
          console.error(`[SYNC] Stack trace: ${error.stack}`);
        }
      }
    }

    const duration = Date.now() - startTime;
    console.log(`[SYNC] ${usingLegacyMethod ? 'LEGACY' : 'OPTIMIZED'} sync complete. Synced ${synced}/${wallets.length} wallets in ${duration}ms`);

    // Update last tracker update timestamp
    this.lastTrackerUpdate = this.getLatestTrackerUpdate();

    // Verify the data was written to the dashboard database
    try {
      const verifyCount = this.dashboardDb.getAllWallets().length;
      console.log(`[SYNC] Verification: Dashboard database now contains ${verifyCount} wallets`);
    } catch (error) {
      console.error('[SYNC] Failed to verify dashboard database:', error);
    }
  }

  /**
   * Optimized single-query retrieval from unified wallet_dashboard_summary table
   * All metrics are pre-calculated by the tracker, eliminating need for joins
   */
  private getWalletStatsOptimized(wallet: string): WalletStats | null {
    const summary = this.trackerDb
      .prepare(`SELECT * FROM wallet_dashboard_summary WHERE wallet = ?`)
      .get(wallet) as any;

    if (!summary) return null;

    // Direct mapping from unified summary table to WalletStats
    const stats: WalletStats = {
      wallet,

      // Today/Recent Activity
      profit_24h: summary.profit_24h || 0,
      recent_trade_market: summary.recent_trade_market || null,
      recent_trade_side: summary.recent_trade_side || null,
      recent_trade_timestamp: summary.recent_trade_timestamp || null,
      recent_trade_pnl: summary.recent_trade_pnl || null,
      avg_time_between_positions: summary.avg_time_between_positions || 0,
      last_position_timestamp: summary.last_position_timestamp || null,

      // 7-Day Track Record
      win_rate: summary.win_rate || 0,
      total_trades: summary.total_trades || 0,
      avg_trades_per_day: summary.avg_trades_per_day || 0,
      avg_hold_time_seconds: summary.avg_hold_time_seconds || 0,

      // Performance Metrics from Closed Positions
      avg_win: summary.avg_win || 0,
      avg_loss: summary.avg_loss || 0,
      best_trade_amount: summary.best_trade_amount || 0,
      best_trade_time_ago: summary.best_trade_time_ago || null,
      best_perf_amount: summary.best_trade_amount || 0, // Same as best trade
      best_perf_time_ago: summary.best_trade_time_ago || null,
      worst_perf_amount: summary.worst_trade_amount || 0,
      worst_perf_time_ago: summary.worst_trade_time_ago || null,
      num_wins: summary.num_wins || 0,
      num_losses: summary.num_losses || 0,
      avg_trade_size: summary.avg_trade_size || 0,
      profit_factor: summary.profit_factor || 0,

      last_updated: summary.last_updated || Math.floor(Date.now() / 1000),
    };

    return stats;
  }

  // Legacy method kept for fallback - no longer used in primary sync path
  private calculateWalletStats(
    wallet: string,
    sevenDaysAgo: number,
    oneDayAgo: number
  ): WalletStats | null {
    // Get all stats for this wallet
    // Note: We don't filter by sevenDaysAgo here because we might be syncing old data
    const statsRows = this.trackerDb
      .prepare(
        `SELECT * FROM wallet_stats_7d
         WHERE wallet = ?
         ORDER BY as_of_ts DESC`
      )
      .all(wallet) as any[];

    if (statsRows.length === 0) return null;

    // Use the most recent stats snapshot as base
    const latestStats = statsRows[0];

    // Get position history for this wallet
    // Note: We don't filter by sevenDaysAgo to get all available data
    const positions = this.trackerDb
      .prepare(
        `SELECT mp.*, se.trigger_ts, se.market_id, m.title as market_title, m.timeframe
         FROM market_positions mp
         JOIN scan_events se ON mp.scan_event_id = se.id
         JOIN markets m ON se.market_id = m.market_id
         WHERE mp.wallet = ?
         ORDER BY se.trigger_ts DESC`
      )
      .all(wallet) as any[];

    // Calculate 24h profit (simplified - would need actual trade outcomes)
    const recentPositions = positions.filter((p) => p.trigger_ts >= oneDayAgo);
    const profit24h = this.estimateProfit24h(recentPositions);

    // Get most recent trade
    const recentTrade = positions[0] || null;

    // Calculate average time between positions
    const avgTimeBetween = this.calculateAvgTimeBetween(positions);

    // Get actual P&L metrics from top_wallet_performance table (preferred)
    // This contains performance metrics calculated from real closed positions
    const performanceMetrics = this.trackerDb
      .prepare(
        `SELECT * FROM top_wallet_performance
         WHERE wallet = ?
         ORDER BY id DESC
         LIMIT 1`
      )
      .get(wallet) as any;

    // Use actual P&L metrics if available, otherwise fall back to estimates
    let numWins, numLosses, avgWin, avgLoss, bestTrade, worstPerf, profitFactor;

    if (performanceMetrics) {
      // Use actual metrics from closed positions (top_wallet_performance table)
      numWins = performanceMetrics.num_wins;
      numLosses = performanceMetrics.num_losses;
      avgWin = performanceMetrics.avg_win;
      avgLoss = performanceMetrics.avg_loss;
      profitFactor = performanceMetrics.profit_factor;
      bestTrade = {
        amount: performanceMetrics.best_trade,
        timestamp: latestStats.as_of_ts,
      };
      worstPerf = {
        amount: performanceMetrics.worst_trade,
        timestamp: latestStats.as_of_ts,
      };
    } else {
      // Fall back to estimated metrics from top_wallet_picks
      const estimates = this.calculateWinLossMetrics(wallet, sevenDaysAgo);
      numWins = estimates.numWins;
      numLosses = estimates.numLosses;
      avgWin = estimates.avgWin;
      avgLoss = estimates.avgLoss;
      bestTrade = estimates.bestTrade;
      worstPerf = estimates.worstPerf;

      // Calculate profit factor from estimates
      const totalProfits = numWins * avgWin;
      const totalLosses = Math.abs(numLosses * avgLoss);
      profitFactor = totalLosses > 0 ? totalProfits / totalLosses : 0;
    }

    // Calculate average trade size
    const avgTradeSize = latestStats.avg_trade_size || 0;

    const stats: WalletStats = {
      wallet,

      // Today metrics
      profit_24h: profit24h,
      recent_trade_market: recentTrade?.market_title || null,
      recent_trade_side: recentTrade?.side || null,
      recent_trade_timestamp: recentTrade?.trigger_ts || null,
      recent_trade_pnl: this.estimateTradePnl(recentTrade),
      avg_time_between_positions: avgTimeBetween,
      last_position_timestamp: recentTrade?.trigger_ts || null,

      // Track record (7-day)
      win_rate: latestStats.win_rate || 0,
      total_trades: latestStats.trade_count || 0,
      avg_trades_per_day: (latestStats.trade_count || 0) / 7,
      avg_hold_time_seconds: this.calculateAvgHoldTime(positions),
      avg_win: avgWin,
      avg_loss: avgLoss,
      best_trade_amount: bestTrade.amount,
      best_trade_time_ago: bestTrade.timestamp,
      best_perf_amount: bestTrade.amount, // Same as best trade for now
      best_perf_time_ago: bestTrade.timestamp,
      worst_perf_amount: worstPerf.amount,
      worst_perf_time_ago: worstPerf.timestamp,
      num_wins: numWins,
      num_losses: numLosses,
      avg_trade_size: avgTradeSize,
      profit_factor: profitFactor,

      last_updated: Math.floor(Date.now() / 1000),
    };

    return stats;
  }

  private estimateProfit24h(positions: any[]): number {
    // Simplified: sum of position values (would need actual P&L data)
    return positions.reduce((sum, p) => sum + (p.value || 0), 0);
  }

  private estimateTradePnl(trade: any): number | null {
    if (!trade) return null;
    // Simplified estimation - would need actual exit price
    return trade.value * 0.05; // Placeholder
  }

  private calculateAvgTimeBetween(positions: any[]): number {
    if (positions.length < 2) return 0;

    const timestamps = positions.map((p) => p.trigger_ts).sort((a, b) => a - b);
    const intervals = [];

    for (let i = 1; i < timestamps.length; i++) {
      intervals.push(timestamps[i] - timestamps[i - 1]);
    }

    return intervals.length > 0
      ? Math.floor(intervals.reduce((sum, val) => sum + val, 0) / intervals.length)
      : 0;
  }

  private calculateAvgHoldTime(positions: any[]): number {
    // NOTE: This legacy method uses scanner positions, not closed positions
    // The tracker database's wallet_dashboard_summary table now contains
    // avg_hold_time_seconds calculated from actual closed positions via Polymarket API.
    // This fallback should rarely be used.

    if (positions.length < 2) return 300;

    // Calculate time between consecutive positions as a rough approximation
    const timestamps = positions
      .map((p) => p.trigger_ts)
      .filter((ts) => ts)
      .sort((a, b) => a - b);

    if (timestamps.length < 2) return 300;

    const intervals = [];
    for (let i = 1; i < timestamps.length; i++) {
      intervals.push(timestamps[i] - timestamps[i - 1]);
    }

    return intervals.length > 0
      ? Math.floor(intervals.reduce((sum, val) => sum + val, 0) / intervals.length)
      : 300; // Default 5 minutes
  }

  private calculateWinLossMetrics(wallet: string, sevenDaysAgo: number): {
    numWins: number;
    numLosses: number;
    avgWin: number;
    avgLoss: number;
    bestTrade: { amount: number; timestamp: number | null };
    worstPerf: { amount: number; timestamp: number | null };
  } {
    // This is a simplified calculation
    // In reality, you'd need actual trade outcomes

    const picks = this.trackerDb
      .prepare(
        `SELECT twp.*, se.trigger_ts
         FROM top_wallet_picks twp
         JOIN scan_events se ON twp.scan_event_id = se.id
         WHERE twp.wallet = ? AND se.trigger_ts >= ?`
      )
      .all(wallet, sevenDaysAgo) as any[];

    // Estimate based on rank_score and copyability_score
    const wins = picks.filter((p) => p.rank_score > 0.5);
    const losses = picks.filter((p) => p.rank_score <= 0.5);

    const avgWin = wins.length > 0
      ? wins.reduce((sum, p) => sum + p.rank_score * 100, 0) / wins.length
      : 0;

    const avgLoss = losses.length > 0
      ? -1 * Math.abs(losses.reduce((sum, p) => sum + (p.rank_score - 0.5) * 100, 0) / losses.length)
      : 0;

    const bestPick = picks.length > 0
      ? picks.reduce((best, p) => (p.rank_score > best.rank_score ? p : best), picks[0])
      : null;

    const worstPick = picks.length > 0
      ? picks.reduce((worst, p) => (p.rank_score < worst.rank_score ? p : worst), picks[0])
      : null;

    return {
      numWins: wins.length,
      numLosses: losses.length,
      avgWin,
      avgLoss,
      bestTrade: {
        amount: bestPick ? bestPick.rank_score * 100 : 0,
        timestamp: bestPick?.trigger_ts || null,
      },
      worstPerf: {
        amount: worstPick ? (worstPick.rank_score - 1) * 100 : 0,
        timestamp: worstPick?.trigger_ts || null,
      },
    };
  }

  close(): void {
    this.trackerDb.close();
    this.dashboardDb.close();
  }
}

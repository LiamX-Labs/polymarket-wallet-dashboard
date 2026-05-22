import Database from 'better-sqlite3';
import { DashboardDB } from './db';
import { WalletStats } from './types';

export class SyncService {
  private trackerDb: Database.Database;
  private dashboardDb: DashboardDB;

  constructor(trackerDbPath: string, dashboardDbPath: string) {
    this.trackerDb = new Database(trackerDbPath, { readonly: true });
    this.dashboardDb = new DashboardDB(dashboardDbPath);
  }

  /**
   * Sync wallet data from tracker database
   * Calculates all metrics based on last 7 days of data
   */
  sync(): void {
    console.log('[SYNC] Starting wallet stats sync...');
    const startTime = Date.now();

    const sevenDaysAgo = Math.floor(Date.now() / 1000) - 7 * 24 * 60 * 60;
    const oneDayAgo = Math.floor(Date.now() / 1000) - 24 * 60 * 60;

    // Get all unique wallets from the last 7 days
    // NOTE: If no wallets found in last 7 days, we'll sync ALL wallets
    let wallets = this.trackerDb
      .prepare(
        `SELECT DISTINCT wallet
         FROM wallet_stats_7d
         WHERE as_of_ts >= ?`
      )
      .all(sevenDaysAgo) as Array<{ wallet: string }>;

    console.log(`[SYNC] Found ${wallets.length} unique wallets in the last 7 days`);

    // Fallback: If no recent data, sync all wallets
    if (wallets.length === 0) {
      console.log('[SYNC] No wallets found in last 7 days, syncing ALL wallets from database...');
      wallets = this.trackerDb
        .prepare(`SELECT DISTINCT wallet FROM wallet_stats_7d`)
        .all() as Array<{ wallet: string }>;
      console.log(`[SYNC] Found ${wallets.length} total wallets in database`);
    }

    let synced = 0;
    for (const { wallet } of wallets) {
      try {
        const stats = this.calculateWalletStats(wallet, sevenDaysAgo, oneDayAgo);
        if (stats) {
          this.dashboardDb.upsertWalletStats(stats);
          synced++;
        }
      } catch (error) {
        console.error(`[SYNC] Error processing wallet ${wallet}:`, error);
      }
    }

    const duration = Date.now() - startTime;
    console.log(`[SYNC] Complete. Synced ${synced}/${wallets.length} wallets in ${duration}ms`);
  }

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

    // Calculate wins/losses from top_wallet_picks performance
    const { numWins, numLosses, avgWin, avgLoss, bestTrade, worstPerf } =
      this.calculateWinLossMetrics(wallet, sevenDaysAgo);

    // Calculate average trade size
    const avgTradeSize = latestStats.avg_trade_size || 0;

    // Calculate profit factor
    const totalWins = numWins * avgWin;
    const totalLosses = Math.abs(numLosses * avgLoss);
    const profitFactor = totalLosses > 0 ? totalWins / totalLosses : 0;

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
    // Group positions by market to calculate hold time
    const markets = new Map<string, any[]>();

    for (const pos of positions) {
      if (!markets.has(pos.market_id)) {
        markets.set(pos.market_id, []);
      }
      markets.get(pos.market_id)!.push(pos);
    }

    const holdTimes: number[] = [];

    for (const [marketId, marketPositions] of markets) {
      if (marketPositions.length < 2) continue;

      // Sort by timestamp
      marketPositions.sort((a, b) => a.trigger_ts - b.trigger_ts);

      // Calculate time between entry and exit (simplified)
      const entryTime = marketPositions[0].trigger_ts;
      const exitTime = marketPositions[marketPositions.length - 1].trigger_ts;
      holdTimes.push(exitTime - entryTime);
    }

    return holdTimes.length > 0
      ? Math.floor(holdTimes.reduce((sum, val) => sum + val, 0) / holdTimes.length)
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

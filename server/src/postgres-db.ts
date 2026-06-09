import { asRows, getSql } from './pg';
import { DashboardDatabase } from './db-interface';
import { WalletStats } from './types';

const VALID_SORT_COLUMNS = [
  'wallet', 'profit_24h', 'win_rate', 'total_trades', 'avg_trades_per_day',
  'best_trade_amount', 'profit_factor', 'last_updated', 'avg_trade_size',
  'recent_trade_timestamp', 'avg_win', 'avg_loss', 'num_wins', 'num_losses',
] as const;

export class PostgresDashboardDB implements DashboardDatabase {
  private initialized = false;

  async initSchema(): Promise<void> {
    if (this.initialized) return;
    const sql = getSql();

    await sql`
      CREATE TABLE IF NOT EXISTS wallet_dashboard_stats (
        wallet TEXT PRIMARY KEY,
        profit_24h DOUBLE PRECISION NOT NULL DEFAULT 0,
        recent_trade_market TEXT,
        recent_trade_side TEXT,
        recent_trade_timestamp BIGINT,
        recent_trade_pnl DOUBLE PRECISION,
        avg_time_between_positions INTEGER NOT NULL DEFAULT 0,
        last_position_timestamp BIGINT,
        win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
        total_trades INTEGER NOT NULL DEFAULT 0,
        avg_trades_per_day DOUBLE PRECISION NOT NULL DEFAULT 0,
        avg_hold_time_seconds INTEGER NOT NULL DEFAULT 0,
        avg_win DOUBLE PRECISION NOT NULL DEFAULT 0,
        avg_loss DOUBLE PRECISION NOT NULL DEFAULT 0,
        best_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        best_trade_time_ago BIGINT,
        worst_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        worst_trade_time_ago BIGINT,
        best_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        best_perf_time_ago BIGINT,
        best_perf_count INTEGER NOT NULL DEFAULT 0,
        worst_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        worst_perf_time_ago BIGINT,
        worst_perf_count INTEGER NOT NULL DEFAULT 0,
        num_wins INTEGER NOT NULL DEFAULT 0,
        num_losses INTEGER NOT NULL DEFAULT 0,
        avg_trade_size DOUBLE PRECISION NOT NULL DEFAULT 0,
        profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0,
        last_updated BIGINT NOT NULL
      )
    `;

    await sql`CREATE INDEX IF NOT EXISTS idx_stats_profit_24h ON wallet_dashboard_stats (profit_24h)`;
    await sql`CREATE INDEX IF NOT EXISTS idx_stats_win_rate ON wallet_dashboard_stats (win_rate)`;
    await sql`CREATE INDEX IF NOT EXISTS idx_stats_last_updated ON wallet_dashboard_stats (last_updated)`;

    await sql`
      CREATE TABLE IF NOT EXISTS wallet_dashboard_summary (
        wallet TEXT PRIMARY KEY,
        profit_24h DOUBLE PRECISION NOT NULL DEFAULT 0,
        recent_trade_market TEXT,
        recent_trade_side TEXT,
        recent_trade_timestamp BIGINT,
        recent_trade_pnl DOUBLE PRECISION,
        avg_time_between_positions INTEGER NOT NULL DEFAULT 0,
        last_position_timestamp BIGINT,
        win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
        total_trades INTEGER NOT NULL DEFAULT 0,
        avg_trades_per_day DOUBLE PRECISION NOT NULL DEFAULT 0,
        avg_hold_time_seconds INTEGER NOT NULL DEFAULT 0,
        total_profits DOUBLE PRECISION NOT NULL DEFAULT 0,
        total_losses DOUBLE PRECISION NOT NULL DEFAULT 0,
        profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0,
        num_wins INTEGER NOT NULL DEFAULT 0,
        num_losses INTEGER NOT NULL DEFAULT 0,
        avg_win DOUBLE PRECISION NOT NULL DEFAULT 0,
        avg_loss DOUBLE PRECISION NOT NULL DEFAULT 0,
        best_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        best_trade_time_ago BIGINT,
        worst_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        worst_trade_time_ago BIGINT,
        best_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        best_perf_count INTEGER NOT NULL DEFAULT 0,
        worst_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        worst_perf_count INTEGER NOT NULL DEFAULT 0,
        avg_trade_size DOUBLE PRECISION NOT NULL DEFAULT 0,
        last_updated BIGINT NOT NULL,
        scan_event_id INTEGER
      )
    `;

    this.initialized = true;
    console.log('[DB] PostgreSQL schema ready');
  }

  async upsertWalletStats(stats: WalletStats): Promise<void> {
    await this.initSchema();
    const sql = getSql();
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
      ) VALUES (
        ${stats.wallet}, ${stats.profit_24h}, ${stats.recent_trade_market},
        ${stats.recent_trade_side}, ${stats.recent_trade_timestamp},
        ${stats.recent_trade_pnl}, ${stats.avg_time_between_positions},
        ${stats.last_position_timestamp}, ${stats.win_rate}, ${stats.total_trades},
        ${stats.avg_trades_per_day}, ${stats.avg_hold_time_seconds},
        ${stats.avg_win}, ${stats.avg_loss}, ${stats.best_trade_amount},
        ${stats.best_trade_time_ago}, ${stats.worst_trade_amount},
        ${stats.worst_trade_time_ago}, ${stats.best_perf_amount},
        ${stats.best_perf_time_ago}, ${stats.best_perf_count},
        ${stats.worst_perf_amount}, ${stats.worst_perf_time_ago},
        ${stats.worst_perf_count}, ${stats.num_wins}, ${stats.num_losses},
        ${stats.avg_trade_size}, ${stats.profit_factor}, ${stats.last_updated}
      )
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
        best_perf_time_ago = EXCLUDED.best_perf_time_ago,
        best_perf_count = EXCLUDED.best_perf_count,
        worst_perf_amount = EXCLUDED.worst_perf_amount,
        worst_perf_time_ago = EXCLUDED.worst_perf_time_ago,
        worst_perf_count = EXCLUDED.worst_perf_count,
        num_wins = EXCLUDED.num_wins,
        num_losses = EXCLUDED.num_losses,
        avg_trade_size = EXCLUDED.avg_trade_size,
        profit_factor = EXCLUDED.profit_factor,
        last_updated = EXCLUDED.last_updated
    `;
  }

  async getAllWallets(sortBy = 'profit_24h', order: 'asc' | 'desc' = 'desc'): Promise<WalletStats[]> {
    await this.initSchema();
    const sql = getSql();
    const column = VALID_SORT_COLUMNS.includes(sortBy as typeof VALID_SORT_COLUMNS[number])
      ? sortBy
      : 'profit_24h';
    const direction = order === 'asc' ? 'ASC' : 'DESC';

    const rows = asRows<WalletStats>(
      await sql(`SELECT * FROM wallet_dashboard_stats ORDER BY ${column} ${direction}`)
    );
    return rows;
  }

  async getWalletCount(): Promise<number> {
    await this.initSchema();
    const sql = getSql();
    const rows = asRows<{ count: string }>(await sql`
      SELECT COUNT(*)::text AS count FROM wallet_dashboard_stats
    `);
    return Number(rows[0]?.count ?? 0);
  }

  async getWalletByAddress(wallet: string): Promise<WalletStats | undefined> {
    await this.initSchema();
    const sql = getSql();
    const rows = asRows<WalletStats>(await sql`
      SELECT * FROM wallet_dashboard_stats WHERE wallet = ${wallet}
    `);
    return rows[0];
  }

  async close(): Promise<void> {
    // Neon serverless driver is stateless per request
  }
}

import Database from 'better-sqlite3';
import { WalletStats } from './types';

export class DashboardDB {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS wallet_dashboard_stats (
        wallet TEXT PRIMARY KEY,

        -- Today metrics (last 24 hours)
        profit_24h REAL DEFAULT 0,
        recent_trade_market TEXT,
        recent_trade_side TEXT,
        recent_trade_timestamp INTEGER,
        recent_trade_pnl REAL,
        avg_time_between_positions INTEGER DEFAULT 0,
        last_position_timestamp INTEGER,

        -- Track Record metrics (lookback window)
        win_rate REAL DEFAULT 0,
        total_trades INTEGER DEFAULT 0,
        avg_trades_per_day REAL DEFAULT 0,
        avg_hold_time_seconds INTEGER DEFAULT 0,
        avg_win REAL DEFAULT 0,
        avg_loss REAL DEFAULT 0,
        best_trade_amount REAL DEFAULT 0,
        best_trade_time_ago INTEGER,
        worst_trade_amount REAL DEFAULT 0,
        worst_trade_time_ago INTEGER,
        best_perf_amount REAL DEFAULT 0,
        best_perf_time_ago INTEGER,
        best_perf_count INTEGER DEFAULT 0,
        worst_perf_amount REAL DEFAULT 0,
        worst_perf_time_ago INTEGER,
        worst_perf_count INTEGER DEFAULT 0,
        num_wins INTEGER DEFAULT 0,
        num_losses INTEGER DEFAULT 0,
        avg_trade_size REAL DEFAULT 0,
        profit_factor REAL DEFAULT 0,

        last_updated INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_profit_24h    ON wallet_dashboard_stats(profit_24h);
      CREATE INDEX IF NOT EXISTS idx_win_rate      ON wallet_dashboard_stats(win_rate);
      CREATE INDEX IF NOT EXISTS idx_total_trades  ON wallet_dashboard_stats(total_trades);
      CREATE INDEX IF NOT EXISTS idx_last_updated  ON wallet_dashboard_stats(last_updated);
      CREATE INDEX IF NOT EXISTS idx_avg_trade_size ON wallet_dashboard_stats(avg_trade_size);
    `);

    // Migrate existing databases that were created before best_perf_count /
    // worst_perf_count columns existed.
    this.addColumnIfMissing('best_perf_count',  'INTEGER DEFAULT 0');
    this.addColumnIfMissing('worst_perf_count', 'INTEGER DEFAULT 0');
  }

  /** Safely add a column to wallet_dashboard_stats if it does not already exist. */
  private addColumnIfMissing(column: string, definition: string): void {
    try {
      const existing = this.db
        .prepare(`PRAGMA table_info(wallet_dashboard_stats)`)
        .all() as Array<{ name: string }>;
      if (!existing.some((c) => c.name === column)) {
        this.db.exec(
          `ALTER TABLE wallet_dashboard_stats ADD COLUMN ${column} ${definition}`
        );
        console.log(`[DB] Added missing column: ${column}`);
      }
    } catch (err) {
      console.error(`[DB] Failed to add column ${column}:`, err);
    }
  }

  upsertWalletStats(stats: WalletStats): void {
    const stmt = this.db.prepare(`
      INSERT INTO wallet_dashboard_stats (
        wallet, profit_24h, recent_trade_market, recent_trade_side,
        recent_trade_timestamp, recent_trade_pnl, avg_time_between_positions,
        last_position_timestamp, win_rate, total_trades, avg_trades_per_day,
        avg_hold_time_seconds, avg_win, avg_loss, best_trade_amount,
        best_trade_time_ago, worst_trade_amount, worst_trade_time_ago,
        best_perf_amount, best_perf_time_ago, best_perf_count,
        worst_perf_amount, worst_perf_time_ago, worst_perf_count,
        num_wins, num_losses, avg_trade_size,
        profit_factor, last_updated
      ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
      )
      ON CONFLICT(wallet) DO UPDATE SET
        profit_24h = excluded.profit_24h,
        recent_trade_market = excluded.recent_trade_market,
        recent_trade_side = excluded.recent_trade_side,
        recent_trade_timestamp = excluded.recent_trade_timestamp,
        recent_trade_pnl = excluded.recent_trade_pnl,
        avg_time_between_positions = excluded.avg_time_between_positions,
        last_position_timestamp = excluded.last_position_timestamp,
        win_rate = excluded.win_rate,
        total_trades = excluded.total_trades,
        avg_trades_per_day = excluded.avg_trades_per_day,
        avg_hold_time_seconds = excluded.avg_hold_time_seconds,
        avg_win = excluded.avg_win,
        avg_loss = excluded.avg_loss,
        best_trade_amount = excluded.best_trade_amount,
        best_trade_time_ago = excluded.best_trade_time_ago,
        worst_trade_amount = excluded.worst_trade_amount,
        worst_trade_time_ago = excluded.worst_trade_time_ago,
        best_perf_amount = excluded.best_perf_amount,
        best_perf_time_ago = excluded.best_perf_time_ago,
        best_perf_count = excluded.best_perf_count,
        worst_perf_amount = excluded.worst_perf_amount,
        worst_perf_time_ago = excluded.worst_perf_time_ago,
        worst_perf_count = excluded.worst_perf_count,
        num_wins = excluded.num_wins,
        num_losses = excluded.num_losses,
        avg_trade_size = excluded.avg_trade_size,
        profit_factor = excluded.profit_factor,
        last_updated = excluded.last_updated
    `);

    stmt.run(
      stats.wallet,
      stats.profit_24h,
      stats.recent_trade_market,
      stats.recent_trade_side,
      stats.recent_trade_timestamp,
      stats.recent_trade_pnl,
      stats.avg_time_between_positions,
      stats.last_position_timestamp,
      stats.win_rate,
      stats.total_trades,
      stats.avg_trades_per_day,
      stats.avg_hold_time_seconds,
      stats.avg_win,
      stats.avg_loss,
      stats.best_trade_amount,
      stats.best_trade_time_ago,
      stats.worst_trade_amount,
      stats.worst_trade_time_ago,
      stats.best_perf_amount,
      stats.best_perf_time_ago,
      stats.best_perf_count,
      stats.worst_perf_amount,
      stats.worst_perf_time_ago,
      stats.worst_perf_count,
      stats.num_wins,
      stats.num_losses,
      stats.avg_trade_size,
      stats.profit_factor,
      stats.last_updated
    );
  }

  getAllWallets(sortBy: string = 'profit_24h', order: 'asc' | 'desc' = 'desc'): WalletStats[] {
    const validColumns = [
      'wallet', 'profit_24h', 'win_rate', 'total_trades', 'avg_trades_per_day',
      'best_trade_amount', 'profit_factor', 'last_updated', 'avg_trade_size',
      'recent_trade_timestamp', 'avg_win', 'avg_loss', 'num_wins', 'num_losses',
    ];

    const column = validColumns.includes(sortBy) ? sortBy : 'profit_24h';
    const direction = order === 'asc' ? 'ASC' : 'DESC';

    const stmt = this.db.prepare(`
      SELECT * FROM wallet_dashboard_stats
      ORDER BY ${column} ${direction}
    `);

    return stmt.all() as WalletStats[];
  }

  getWalletByAddress(wallet: string): WalletStats | undefined {
    const stmt = this.db.prepare('SELECT * FROM wallet_dashboard_stats WHERE wallet = ?');
    return stmt.get(wallet) as WalletStats | undefined;
  }

  close(): void {
    this.db.close();
  }
}

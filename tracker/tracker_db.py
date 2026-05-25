import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable


class TrackerDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS markets (
                market_id TEXT PRIMARY KEY,
                slug TEXT,
                title TEXT,
                timeframe TEXT,
                start_time TEXT,
                end_time TEXT
            );

            CREATE TABLE IF NOT EXISTS scan_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                trigger_ts INTEGER NOT NULL,
                progress_pct REAL NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(market_id, trigger_ts)
            );

            CREATE TABLE IF NOT EXISTS market_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_event_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                size REAL NOT NULL,
                value REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_stats_7d (
                wallet TEXT NOT NULL,
                as_of_ts INTEGER NOT NULL,
                roi REAL NOT NULL,
                win_rate REAL NOT NULL,
                pnl REAL NOT NULL,
                trade_count INTEGER NOT NULL,
                avg_trade_size REAL NOT NULL,
                hft_flag INTEGER NOT NULL,
                PRIMARY KEY (wallet, as_of_ts)
            );

            CREATE TABLE IF NOT EXISTS top_wallet_picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_event_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                side TEXT NOT NULL,
                rank_score REAL NOT NULL,
                copyability_score REAL NOT NULL,
                timeframe TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_wallet_summary (
                date_utc TEXT NOT NULL,
                wallet TEXT NOT NULL,
                appearances INTEGER NOT NULL,
                aggregate_score REAL NOT NULL,
                specialization TEXT,
                PRIMARY KEY (date_utc, wallet)
            );

            CREATE TABLE IF NOT EXISTS wallet_stats_30d (
                wallet TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                roi REAL NOT NULL,
                win_rate REAL NOT NULL,
                pnl REAL NOT NULL,
                avg_trade_size REAL NOT NULL,
                specialization TEXT,
                PRIMARY KEY (wallet, as_of_date)
            );

            CREATE TABLE IF NOT EXISTS wallet_pnl_metrics_7d (
                wallet TEXT NOT NULL,
                as_of_ts INTEGER NOT NULL,
                total_profits REAL NOT NULL,
                total_losses REAL NOT NULL,
                profit_factor REAL NOT NULL,
                num_wins INTEGER NOT NULL,
                num_losses INTEGER NOT NULL,
                avg_win REAL NOT NULL,
                avg_loss REAL NOT NULL,
                best_trade REAL NOT NULL,
                worst_trade REAL NOT NULL,
                PRIMARY KEY (wallet, as_of_ts)
            );

            CREATE TABLE IF NOT EXISTS top_wallet_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_event_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                market_id TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                size REAL NOT NULL,
                value REAL NOT NULL,
                rank_score REAL NOT NULL,
                copyability_score REAL NOT NULL,
                total_profits REAL NOT NULL,
                total_losses REAL NOT NULL,
                profit_factor REAL NOT NULL,
                num_wins INTEGER NOT NULL,
                num_losses INTEGER NOT NULL,
                avg_win REAL NOT NULL,
                avg_loss REAL NOT NULL,
                best_trade REAL NOT NULL,
                worst_trade REAL NOT NULL,
                FOREIGN KEY (scan_event_id) REFERENCES scan_events(id)
            );

            CREATE INDEX IF NOT EXISTS idx_top_wallet_performance_scan
                ON top_wallet_performance(scan_event_id);
            CREATE INDEX IF NOT EXISTS idx_top_wallet_performance_wallet
                ON top_wallet_performance(wallet);

            -- Optimized unified wallet summary table for dashboard
            -- Denormalized for single-query retrieval
            CREATE TABLE IF NOT EXISTS wallet_dashboard_summary (
                wallet TEXT PRIMARY KEY,

                -- Today/Recent Activity
                profit_24h REAL NOT NULL DEFAULT 0,
                recent_trade_market TEXT,
                recent_trade_side TEXT,
                recent_trade_timestamp INTEGER,
                recent_trade_pnl REAL,
                avg_time_between_positions INTEGER NOT NULL DEFAULT 0,
                last_position_timestamp INTEGER,

                -- 7-Day Track Record
                win_rate REAL NOT NULL DEFAULT 0,
                total_trades INTEGER NOT NULL DEFAULT 0,
                avg_trades_per_day REAL NOT NULL DEFAULT 0,
                avg_hold_time_seconds INTEGER NOT NULL DEFAULT 0,

                -- Performance Metrics from Closed Positions
                total_profits REAL NOT NULL DEFAULT 0,
                total_losses REAL NOT NULL DEFAULT 0,
                profit_factor REAL NOT NULL DEFAULT 0,
                num_wins INTEGER NOT NULL DEFAULT 0,
                num_losses INTEGER NOT NULL DEFAULT 0,
                avg_win REAL NOT NULL DEFAULT 0,
                avg_loss REAL NOT NULL DEFAULT 0,
                best_trade_amount REAL NOT NULL DEFAULT 0,
                best_trade_time_ago INTEGER,
                worst_trade_amount REAL NOT NULL DEFAULT 0,
                worst_trade_time_ago INTEGER,
                avg_trade_size REAL NOT NULL DEFAULT 0,

                -- Metadata
                last_updated INTEGER NOT NULL,
                scan_event_id INTEGER,

                FOREIGN KEY (scan_event_id) REFERENCES scan_events(id)
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_dashboard_updated
                ON wallet_dashboard_summary(last_updated DESC);
            CREATE INDEX IF NOT EXISTS idx_wallet_dashboard_profit
                ON wallet_dashboard_summary(profit_24h DESC);
            CREATE INDEX IF NOT EXISTS idx_wallet_dashboard_profit_factor
                ON wallet_dashboard_summary(profit_factor DESC);
            """
        )
        self.conn.commit()

    def upsert_market(self, market: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO markets (market_id, slug, title, timeframe, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_id) DO UPDATE SET
              slug=excluded.slug, title=excluded.title, timeframe=excluded.timeframe,
              start_time=excluded.start_time, end_time=excluded.end_time
            """,
            (
                market["market_id"],
                market["slug"],
                market["title"],
                market["timeframe"],
                market["start_time"],
                market["end_time"],
            ),
        )
        self.conn.commit()

    def scan_exists(self, market_id: str, trigger_ts: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM scan_events WHERE market_id = ? AND trigger_ts = ?",
            (market_id, trigger_ts),
        ).fetchone()
        return row is not None

    def create_scan_event(self, market_id: str, trigger_ts: int, progress_pct: float) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO scan_events (market_id, trigger_ts, progress_pct, status)
            VALUES (?, ?, ?, ?)
            """,
            (market_id, trigger_ts, progress_pct, "ok"),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_positions(self, scan_event_id: int, positions: Iterable[dict[str, Any]]) -> None:
        self.conn.executemany(
            """
            INSERT INTO market_positions (scan_event_id, wallet, side, entry_price, size, value)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_event_id,
                    p["wallet"],
                    p["side"],
                    p["entry_price"],
                    p["size"],
                    p["value"],
                )
                for p in positions
            ],
        )
        self.conn.commit()

    def save_wallet_stats_7d(self, stats: Iterable[dict[str, Any]]) -> None:
        as_of_ts = int(datetime.now(timezone.utc).timestamp())
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO wallet_stats_7d
            (wallet, as_of_ts, roi, win_rate, pnl, trade_count, avg_trade_size, hft_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    s["wallet"],
                    as_of_ts,
                    s["roi"],
                    s["win_rate"],
                    s["pnl"],
                    s["trade_count"],
                    s["avg_trade_size"],
                    1 if s["hft_flag"] else 0,
                )
                for s in stats
            ],
        )
        self.conn.commit()

    def save_top_wallet_picks(self, scan_event_id: int, picks: Iterable[dict[str, Any]], timeframe: str) -> None:
        self.conn.executemany(
            """
            INSERT INTO top_wallet_picks
            (scan_event_id, wallet, side, rank_score, copyability_score, timeframe)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_event_id,
                    p["wallet"],
                    p["side"],
                    p["rank_score"],
                    p["copyability_score"],
                    timeframe,
                )
                for p in picks
            ],
        )
        self.conn.commit()

    def top_wallets_for_date(self, date_utc: str, limit: int = 10) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT wallet,
                       COUNT(*) AS appearances,
                       AVG(rank_score) AS aggregate_score
                FROM top_wallet_picks t
                JOIN scan_events s ON t.scan_event_id = s.id
                WHERE date(datetime(s.trigger_ts, 'unixepoch')) = ?
                GROUP BY wallet
                ORDER BY aggregate_score DESC, appearances DESC
                LIMIT ?
                """,
                (date_utc, limit),
            ).fetchall()
        )

    def save_daily_summary(self, date_utc: str, summary_rows: Iterable[dict[str, Any]]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO daily_wallet_summary
            (date_utc, wallet, appearances, aggregate_score, specialization)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    date_utc,
                    row["wallet"],
                    row["appearances"],
                    row["aggregate_score"],
                    row["specialization"],
                )
                for row in summary_rows
            ],
        )
        self.conn.commit()

    def save_wallet_pnl_metrics_7d(self, metrics: Iterable[dict[str, Any]]) -> None:
        """Save P&L metrics calculated from actual closed positions."""
        as_of_ts = int(datetime.now(timezone.utc).timestamp())
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO wallet_pnl_metrics_7d
            (wallet, as_of_ts, total_profits, total_losses, profit_factor,
             num_wins, num_losses, avg_win, avg_loss, best_trade, worst_trade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    m["wallet"],
                    as_of_ts,
                    m["total_profits"],
                    m["total_losses"],
                    m["profit_factor"],
                    m["num_wins"],
                    m["num_losses"],
                    m["avg_win"],
                    m["avg_loss"],
                    m["best_trade"],
                    m["worst_trade"],
                )
                for m in metrics
            ],
        )
        self.conn.commit()

    def save_top_wallet_performance(self, performance_data: Iterable[dict[str, Any]]) -> None:
        """Save performance metrics for top wallets with closed positions data."""
        self.conn.executemany(
            """
            INSERT INTO top_wallet_performance
            (scan_event_id, wallet, market_id, side, entry_price, size, value,
             rank_score, copyability_score, total_profits, total_losses, profit_factor,
             num_wins, num_losses, avg_win, avg_loss, best_trade, worst_trade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    p["scan_event_id"],
                    p["wallet"],
                    p["market_id"],
                    p["side"],
                    p["entry_price"],
                    p["size"],
                    p["value"],
                    p["rank_score"],
                    p["copyability_score"],
                    p["total_profits"],
                    p["total_losses"],
                    p["profit_factor"],
                    p["num_wins"],
                    p["num_losses"],
                    p["avg_win"],
                    p["avg_loss"],
                    p["best_trade"],
                    p["worst_trade"],
                )
                for p in performance_data
            ],
        )
        self.conn.commit()

    def upsert_wallet_dashboard_summary(self, wallet_data: dict[str, Any]) -> None:
        """
        Upsert complete wallet data into unified dashboard summary table.
        This is a denormalized table optimized for single-query dashboard retrieval.
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO wallet_dashboard_summary
            (wallet, profit_24h, recent_trade_market, recent_trade_side,
             recent_trade_timestamp, recent_trade_pnl, avg_time_between_positions,
             last_position_timestamp, win_rate, total_trades, avg_trades_per_day,
             avg_hold_time_seconds, total_profits, total_losses, profit_factor,
             num_wins, num_losses, avg_win, avg_loss, best_trade_amount,
             best_trade_time_ago, worst_trade_amount, worst_trade_time_ago,
             avg_trade_size, last_updated, scan_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                wallet_data["wallet"],
                wallet_data.get("profit_24h", 0),
                wallet_data.get("recent_trade_market"),
                wallet_data.get("recent_trade_side"),
                wallet_data.get("recent_trade_timestamp"),
                wallet_data.get("recent_trade_pnl"),
                wallet_data.get("avg_time_between_positions", 0),
                wallet_data.get("last_position_timestamp"),
                wallet_data.get("win_rate", 0),
                wallet_data.get("total_trades", 0),
                wallet_data.get("avg_trades_per_day", 0),
                wallet_data.get("avg_hold_time_seconds", 0),
                wallet_data.get("total_profits", 0),
                wallet_data.get("total_losses", 0),
                wallet_data.get("profit_factor", 0),
                wallet_data.get("num_wins", 0),
                wallet_data.get("num_losses", 0),
                wallet_data.get("avg_win", 0),
                wallet_data.get("avg_loss", 0),
                wallet_data.get("best_trade_amount", 0),
                wallet_data.get("best_trade_time_ago"),
                wallet_data.get("worst_trade_amount", 0),
                wallet_data.get("worst_trade_time_ago"),
                wallet_data.get("avg_trade_size", 0),
                int(datetime.now(timezone.utc).timestamp()),
                wallet_data.get("scan_event_id"),
            ),
        )
        self.conn.commit()


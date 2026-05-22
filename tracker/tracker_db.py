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


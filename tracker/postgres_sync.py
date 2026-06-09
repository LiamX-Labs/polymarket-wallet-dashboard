"""Optional PostgreSQL sync for the Python tracker (Vercel Postgres / Neon)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore


def get_postgres_url() -> str | None:
    return (
        os.getenv("POSTGRES_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
    )


class PostgresSync:
    """Mirrors wallet_dashboard_summary writes to PostgreSQL."""

    def __init__(self, url: str):
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for PostgreSQL sync. Install psycopg2-binary.")
        self.url = url
        self._ensure_schema()

    def _connect(self):
        return psycopg2.connect(self.url)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
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
                    """
                )
            conn.commit()

    def upsert_wallet_dashboard_summary(self, wallet_data: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO wallet_dashboard_summary (
                        wallet, profit_24h, recent_trade_market, recent_trade_side,
                        recent_trade_timestamp, recent_trade_pnl, avg_time_between_positions,
                        last_position_timestamp, win_rate, total_trades, avg_trades_per_day,
                        avg_hold_time_seconds, total_profits, total_losses, profit_factor,
                        num_wins, num_losses, avg_win, avg_loss, best_trade_amount,
                        best_trade_time_ago, worst_trade_amount, worst_trade_time_ago,
                        best_perf_amount, best_perf_count, worst_perf_amount, worst_perf_count,
                        avg_trade_size, last_updated, scan_event_id
                    ) VALUES (
                        %(wallet)s, %(profit_24h)s, %(recent_trade_market)s, %(recent_trade_side)s,
                        %(recent_trade_timestamp)s, %(recent_trade_pnl)s, %(avg_time_between_positions)s,
                        %(last_position_timestamp)s, %(win_rate)s, %(total_trades)s, %(avg_trades_per_day)s,
                        %(avg_hold_time_seconds)s, %(total_profits)s, %(total_losses)s, %(profit_factor)s,
                        %(num_wins)s, %(num_losses)s, %(avg_win)s, %(avg_loss)s, %(best_trade_amount)s,
                        %(best_trade_time_ago)s, %(worst_trade_amount)s, %(worst_trade_time_ago)s,
                        %(best_perf_amount)s, %(best_perf_count)s, %(worst_perf_amount)s, %(worst_perf_count)s,
                        %(avg_trade_size)s, %(last_updated)s, %(scan_event_id)s
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
                        total_profits = EXCLUDED.total_profits,
                        total_losses = EXCLUDED.total_losses,
                        profit_factor = EXCLUDED.profit_factor,
                        num_wins = EXCLUDED.num_wins,
                        num_losses = EXCLUDED.num_losses,
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
                        avg_trade_size = EXCLUDED.avg_trade_size,
                        last_updated = EXCLUDED.last_updated,
                        scan_event_id = EXCLUDED.scan_event_id
                    """,
                    {
                        "wallet": wallet_data["wallet"],
                        "profit_24h": wallet_data.get("profit_24h", 0),
                        "recent_trade_market": wallet_data.get("recent_trade_market"),
                        "recent_trade_side": wallet_data.get("recent_trade_side"),
                        "recent_trade_timestamp": wallet_data.get("recent_trade_timestamp"),
                        "recent_trade_pnl": wallet_data.get("recent_trade_pnl"),
                        "avg_time_between_positions": wallet_data.get("avg_time_between_positions", 0),
                        "last_position_timestamp": wallet_data.get("last_position_timestamp"),
                        "win_rate": wallet_data.get("win_rate", 0),
                        "total_trades": wallet_data.get("total_trades", 0),
                        "avg_trades_per_day": wallet_data.get("avg_trades_per_day", 0),
                        "avg_hold_time_seconds": wallet_data.get("avg_hold_time_seconds", 0),
                        "total_profits": wallet_data.get("total_profits", 0),
                        "total_losses": wallet_data.get("total_losses", 0),
                        "profit_factor": wallet_data.get("profit_factor", 0),
                        "num_wins": wallet_data.get("num_wins", 0),
                        "num_losses": wallet_data.get("num_losses", 0),
                        "avg_win": wallet_data.get("avg_win", 0),
                        "avg_loss": wallet_data.get("avg_loss", 0),
                        "best_trade_amount": wallet_data.get("best_trade_amount", 0),
                        "best_trade_time_ago": wallet_data.get("best_trade_time_ago"),
                        "worst_trade_amount": wallet_data.get("worst_trade_amount", 0),
                        "worst_trade_time_ago": wallet_data.get("worst_trade_time_ago"),
                        "best_perf_amount": wallet_data.get("best_perf_amount", 0),
                        "best_perf_count": wallet_data.get("best_perf_count", 0),
                        "worst_perf_amount": wallet_data.get("worst_perf_amount", 0),
                        "worst_perf_count": wallet_data.get("worst_perf_count", 0),
                        "avg_trade_size": wallet_data.get("avg_trade_size", 0),
                        "last_updated": int(datetime.now(timezone.utc).timestamp()),
                        "scan_event_id": wallet_data.get("scan_event_id"),
                    },
                )
            conn.commit()


_postgres_sync: PostgresSync | None = None


def maybe_get_postgres_sync() -> PostgresSync | None:
    global _postgres_sync
    url = get_postgres_url()
    if not url:
        return None
    if _postgres_sync is None:
        _postgres_sync = PostgresSync(url)
    return _postgres_sync

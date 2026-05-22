from datetime import datetime, timedelta, timezone

from .tracker_db import TrackerDB
from .wallet_profiler import WalletProfiler


def run_daily_report(db: TrackerDB, profiler: WalletProfiler, now_utc: datetime | None = None) -> dict:
    now = now_utc or datetime.now(timezone.utc)
    target_date = (now - timedelta(days=1)).date().isoformat()

    top_wallet_rows = db.top_wallets_for_date(target_date, limit=10)
    wallets = [row["wallet"] for row in top_wallet_rows]
    stats_30d = {row["wallet"]: row for row in profiler.profile_30d(wallets)}

    summary_rows = []
    report_wallets = []
    for row in top_wallet_rows:
        stat = stats_30d.get(row["wallet"], {})
        specialization = stat.get("specialization", "mixed")
        summary_rows.append(
            {
                "wallet": row["wallet"],
                "appearances": int(row["appearances"]),
                "aggregate_score": float(row["aggregate_score"]),
                "specialization": specialization,
            }
        )
        report_wallets.append(
            {
                "wallet": row["wallet"],
                "roi_30d": float(stat.get("roi", 0.0)),
                "win_rate_30d": float(stat.get("win_rate", 0.0)),
                "specialization": specialization,
            }
        )

    if summary_rows:
        db.save_daily_summary(target_date, summary_rows)

    return {
        "date_utc": target_date,
        "markets_scanned": len({w["wallet"] for w in report_wallets}),
        "top_wallets": report_wallets,
    }


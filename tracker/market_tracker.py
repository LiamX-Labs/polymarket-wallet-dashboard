#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bot.config import (
    TRACKER_DATABASE_PATH,
    TRACKER_DAILY_REPORT_HOUR_UTC,
    TRACKER_POLL_INTERVAL_SECONDS,
    TRACKER_TRIGGER_TOLERANCE_SECONDS,
    validate_config,
)

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tracker.clob_client import CLOBClient
    from tracker.daily_alpha_report import run_daily_report
    from tracker.gamma_client import GammaClient
    from tracker.notifier import TrackerNotifier
    from tracker.tracker_db import TrackerDB
    from tracker.wallet_profiler import WalletProfiler
else:
    from .clob_client import CLOBClient
    from .daily_alpha_report import run_daily_report
    from .gamma_client import GammaClient
    from .notifier import TrackerNotifier
    from .tracker_db import TrackerDB
    from .wallet_profiler import WalletProfiler


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tracker")


class BTCMarketTracker:
    def __init__(self):
        self.gamma = GammaClient()
        self.clob = CLOBClient()
        self.profiler = WalletProfiler()
        self.db = TrackerDB(TRACKER_DATABASE_PATH)
        self.db.init_schema()
        self.notifier = TrackerNotifier()
        self._last_daily_report_date = None
        self._loop_count = 0
        self._trigger_queue = asyncio.Queue()
        self._processed_triggers = set()  # (market_id, trigger_ts) deduplication
        self._trigger_lock = asyncio.Lock()
        self._worker_tasks = []  # Track worker tasks
        self._max_concurrent_analyses = 2  # Maximum 2 simultaneous analyses
        self._analysis_semaphore = asyncio.Semaphore(2)  # Limit concurrent analyses

    async def run_forever(self) -> None:
        logger.info(
            "Tracker started | poll=%ss trigger_tolerance=%ss db=%s max_concurrent=%s",
            TRACKER_POLL_INTERVAL_SECONDS,
            TRACKER_TRIGGER_TOLERANCE_SECONDS,
            TRACKER_DATABASE_PATH,
            self._max_concurrent_analyses,
        )

        # Start worker tasks for processing trigger queue
        for i in range(self._max_concurrent_analyses):
            task = asyncio.create_task(self._process_trigger_queue(worker_id=i))
            self._worker_tasks.append(task)

        while True:
            self._loop_count += 1
            try:
                await self.scan_once()
                await self.maybe_send_daily_report()
            except Exception as exc:
                logger.exception("Tracker loop error: %s", exc)
            logger.info("Heartbeat | loop=%s next_check_in=%ss", self._loop_count, TRACKER_POLL_INTERVAL_SECONDS)
            await asyncio.sleep(TRACKER_POLL_INTERVAL_SECONDS)

    async def _process_trigger_queue(self, worker_id: int = 0) -> None:
        """Worker task to process triggers from queue concurrently."""
        logger.info("Worker %d started", worker_id)
        while True:
            try:
                market, trigger_ts, progress_pct = await self._trigger_queue.get()
                queue_size = self._trigger_queue.qsize()
                logger.info(
                    "Worker %d picked up trigger | market=%s queue_remaining=%s",
                    worker_id,
                    market.title,
                    queue_size
                )
                try:
                    await self._run_market_scan(market, trigger_ts, progress_pct)
                except Exception as exc:
                    logger.exception("Worker %d error processing trigger for %s: %s", worker_id, market.title, exc)
                finally:
                    self._trigger_queue.task_done()
            except asyncio.CancelledError:
                logger.info("Worker %d cancelled", worker_id)
                break
            except Exception as exc:
                logger.exception("Worker %d queue error: %s", worker_id, exc)

    async def scan_once(self) -> None:
        now = datetime.now(timezone.utc)
        markets = self.gamma.get_active_btc_markets()
        logger.info("Scan cycle | active_btc_markets=%s utc=%s", len(markets), now.isoformat())

        triggered_count = 0

        for market in markets:
            self.db.upsert_market(
                {
                    "market_id": market.market_id,
                    "slug": market.slug,
                    "title": market.title,
                    "timeframe": market.timeframe,
                    "start_time": market.start_time.isoformat(),
                    "end_time": market.end_time.isoformat(),
                }
            )

            elapsed = (now - market.start_time).total_seconds()
            trigger_ts = int(market.start_time.timestamp() + 0.8 * market.duration_seconds)
            progress_pct = max(0.0, min(100.0, (elapsed / market.duration_seconds) * 100.0))

            if int(now.timestamp()) < trigger_ts:
                continue
            if abs(int(now.timestamp()) - trigger_ts) > TRACKER_TRIGGER_TOLERANCE_SECONDS:
                continue
            if self.db.scan_exists(market.market_id, trigger_ts):
                continue

            # Deduplication: check if we've already queued this trigger
            trigger_key = (market.market_id, trigger_ts)
            async with self._trigger_lock:
                if trigger_key in self._processed_triggers:
                    continue
                self._processed_triggers.add(trigger_key)

            # Queue the trigger for async processing
            await self._trigger_queue.put((market, trigger_ts, progress_pct))
            triggered_count += 1

        logger.info("Scan cycle complete | triggered_scans=%s", triggered_count)

    async def _run_market_scan(self, market, trigger_ts: int, progress_pct: float) -> None:
        logger.info(
            "Trigger hit | market=%s timeframe=%s progress=%.2f%%",
            market.title,
            market.timeframe,
            progress_pct,
        )

        # Use numeric_id for Data API if available
        market_identifier = market.numeric_id if market.numeric_id else market.market_id

        # Step 1: Get top wallets by position value in THIS market only
        pnl_limit = 50  # Fetch top 50 by position value
        pnl_rankings = self.clob.get_market_pnl_rankings(market_identifier, limit=pnl_limit)

        if not pnl_rankings:
            # Fallback: use position size if no trades data available
            logger.warning("No position data for market %s, falling back to position size", market.title)
            sample_size = 5 if market.timeframe in {"5m", "15m"} else 10
            snapshots = self.clob.get_top_positions(market_identifier, sample_size=sample_size)
            all_positions = snapshots["UP"] + snapshots["DOWN"]
            wallets = [p.wallet for p in all_positions]
        else:
            # We have position value rankings from trades
            wallets = [r["wallet"] for r in pnl_rankings]
            # Get position details (side, entry price, timestamps) for these wallets
            snapshots = self.clob.get_top_positions(market_identifier, sample_size=pnl_limit)
            all_positions = snapshots["UP"] + snapshots["DOWN"]

        logger.info("Stage 1: Position value filter | wallets=%s ranked_by=position_value", len(wallets))

        # Step 2: HFT Pre-filter using 4-hour activity check
        hft_results = self.profiler.hft_prefilter_4h(wallets)
        hft_map = {r["wallet"]: r["hft_flag"] for r in hft_results}

        non_hft_wallets = [w for w in wallets if not hft_map.get(w, False)]
        logger.info("Stage 2: HFT pre-filter | wallets_before=%s wallets_after=%s", len(wallets), len(non_hft_wallets))

        # Step 3: Deep scan - 7-day performance on top 10 only
        top_10_wallets = non_hft_wallets[:10]
        stats_7d = self.profiler.profile_7d(top_10_wallets) if top_10_wallets else []
        stat_map = {s["wallet"]: s for s in stats_7d}

        logger.info(
            "Stage 3: Deep scan 7d | wallets_scanned=%s wallets_with_btc_history=%s filtered_out=%s",
            len(top_10_wallets),
            len(stats_7d),
            len(top_10_wallets) - len(stats_7d)
        )

        # Step 4: Rank final 10 by 7-day performance
        ranked = []
        for wallet in top_10_wallets:
            ws = stat_map.get(wallet)
            if not ws:
                continue

            # Find position data for this wallet
            pos = next((p for p in all_positions if p.wallet == wallet), None)
            if not pos:
                continue

            rank_score = self.profiler.rank_score(ws)
            copyability = self.profiler.copyability_score(
                position_first_seen_ts=pos.first_seen_ts,
                trigger_ts=trigger_ts,
                size=pos.size,
                hft_flag=ws.get("hft_flag", False),
            )
            ranked.append(
                {
                    "wallet": wallet,
                    "side": pos.side,
                    "entry_price": pos.entry_price,
                    "size": pos.size,
                    "value": pos.value,
                    "rank_score": rank_score,
                    "copyability_score": copyability,
                    "roi_7d": ws["roi"],
                    "win_rate_7d": ws["win_rate"],
                }
            )

        # Sort by 7-day ROI (descending)
        ranked.sort(key=lambda x: x["roi_7d"], reverse=True)
        top_5 = ranked[:5]

        logger.info(
            "Stage 4: Final ranking | total_ranked=%s top_5=%s",
            len(ranked),
            len(top_5),
        )

        # Save to database
        scan_event_id = self.db.create_scan_event(market.market_id, trigger_ts, progress_pct)
        self.db.save_positions(
            scan_event_id,
            [
                {
                    "wallet": p["wallet"],
                    "side": p["side"],
                    "entry_price": p["entry_price"],
                    "size": p["size"],
                    "value": p["value"],
                }
                for p in top_5
            ],
        )
        self.db.save_wallet_stats_7d(stats_7d)
        self.db.save_top_wallet_picks(scan_event_id, top_5, market.timeframe)

        # Send Telegram alert with top 5
        alert_payload = {
            "market": {
                "title": market.title,
                "timeframe": market.timeframe,
                "progress_pct": progress_pct,
            },
            "top_wallets": [
                {
                    "wallet": p["wallet"],
                    "side": p["side"],
                    "entry_price": p["entry_price"],
                    "roi_7d": p["roi_7d"],
                    "win_rate_7d": p["win_rate_7d"],
                    "rank_score": p["rank_score"],
                    "copyability_score": p["copyability_score"],
                }
                for p in top_5
            ],
        }
        await self.notifier.send_market_alert(alert_payload)

    async def maybe_send_daily_report(self) -> None:
        now = datetime.now(timezone.utc)
        if now.hour != TRACKER_DAILY_REPORT_HOUR_UTC:
            return
        day_key = now.date().isoformat()
        if self._last_daily_report_date == day_key:
            return
        report = run_daily_report(self.db, self.profiler, now)
        await self.notifier.send_daily_report(report)
        self._last_daily_report_date = day_key


def main() -> None:
    validate_config()
    # Ensure tracker db parent dir exists.
    os.makedirs(os.path.dirname(TRACKER_DATABASE_PATH), exist_ok=True)
    tracker = BTCMarketTracker()
    print("Tracker is running. Waiting for market scans... (Ctrl+C to stop)")
    asyncio.run(tracker.run_forever())


if __name__ == "__main__":
    main()


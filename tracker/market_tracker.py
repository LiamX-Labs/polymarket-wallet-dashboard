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
    from tracker.wallet_filter_pipeline import WalletFilterPipeline
else:
    from .clob_client import CLOBClient
    from .daily_alpha_report import run_daily_report
    from .gamma_client import GammaClient
    from .notifier import TrackerNotifier
    from .tracker_db import TrackerDB
    from .wallet_profiler import WalletProfiler
    from .wallet_filter_pipeline import WalletFilterPipeline


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
        self.filter_pipeline = WalletFilterPipeline()
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

        # Step 1: Get initial candidate wallets from market positions
        # Limit to top 20 for faster pipeline processing (was 50)
        pnl_limit = 50
        pnl_rankings = self.clob.get_market_pnl_rankings(market_identifier, limit=pnl_limit)

        if not pnl_rankings:
            # Fallback: use position size if no trades data available
            logger.warning("No position data for market %s, falling back to position size", market.title)
            sample_size = 5 if market.timeframe in {"5m", "15m"} else 8
            snapshots = self.clob.get_top_positions(market_identifier, sample_size=sample_size)
            all_positions = snapshots["UP"] + snapshots["DOWN"]
            candidate_wallets = [p.wallet for p in all_positions]
        else:
            # We have position value rankings from trades
            candidate_wallets = [r["wallet"] for r in pnl_rankings]
            # Get position details (side, entry price, timestamps) for these wallets
            snapshots = self.clob.get_top_positions(market_identifier, sample_size=pnl_limit)
            all_positions = snapshots["UP"] + snapshots["DOWN"]

        logger.info(
            "Initial candidate wallets | wallets=%s from_market=%s",
            len(candidate_wallets),
            market.title,
        )

        # Step 2: Run the 4-stage filter pipeline
        # This filters by: profit > $1, hold_time >= 10min, trade_count >= 20, performance criteria
        # Use asyncio.to_thread for the blocking pipeline call
        top_wallets, wallet_data_cache = await asyncio.to_thread(
            self.filter_pipeline.run_pipeline, candidate_wallets, market.title
        )

        # Early exit if no wallets qualify
        if not top_wallets:
            logger.warning(
                "No wallets qualified from pipeline | market=%s",
                market.title,
            )
            # Still save the scan event for record-keeping
            self.db.create_scan_event(market.market_id, trigger_ts, progress_pct)
            return

        # Step 3: Take top 5 qualified wallets for detailed processing
        top_5 = top_wallets[:10]
        logger.info(
            "Final qualified wallets | total_qualified=%s top_5=%s",
            len(top_wallets),
            len(top_5),
        )

        # Step 4: Enrich top 5 with current market position data
        wallet_closed_positions = {}  # Cache for metrics calculations
        enriched_picks = []

        for wallet_data in top_5:
            wallet = wallet_data["wallet"]

            # Find position data for this wallet in current market
            pos = next((p for p in all_positions if p.wallet == wallet), None)

            try:
                # Reuse positions from pipeline cache if available, else fallback to fetch
                # Note: pipeline uses configurable lookback, which is sufficient for recent performance
                if wallet in wallet_data_cache:
                    positions = wallet_data_cache[wallet]
                else:
                    logger.debug("Cache miss for %s, fetching data", wallet[:8])
                    positions = self.profiler.get_all_positions_lookback(wallet, days=self.filter_pipeline.lookback_days)
                
                wallet_closed_positions[wallet] = positions

                # Calculate scores for database
                rank_score = self.profiler.rank_score({
                    "roi": wallet_data.get("roi", 0.0),
                    "win_rate": wallet_data.get("win_rate", 0.0),
                    "trade_count": wallet_data.get("num_trades", 0)
                })
                
                # Check for HFT (used in copyability)
                hft_flag = self.profiler.is_hft_from_positions(positions) if positions else False
                
                copy_score = self.profiler.copyability_score(
                    position_first_seen_ts=pos.first_seen_ts if pos else None,
                    trigger_ts=trigger_ts,
                    size=pos.size if pos else 0.0,
                    hft_flag=hft_flag
                )

                enriched_picks.append({
                    "wallet": wallet,
                    "side": pos.side if pos else "UNKNOWN",
                    "entry_price": pos.entry_price if pos else 0.0,
                    "size": pos.size if pos else 0.0,
                    "value": pos.value if pos else 0.0,
                    "roi_4d": wallet_data.get("roi", 0.0),
                    "win_rate_4d": wallet_data.get("win_rate", 0.0),
                    "avg_return_per_trade": wallet_data.get("avg_return_per_trade", 0.0),
                    "num_trades": wallet_data.get("num_trades", 0),
                    "rank_score": rank_score,
                    "copyability_score": copy_score,
                })
            except Exception as e:
                logger.warning(
                    "Failed to enrich wallet %s: %s, skipping",
                    wallet[:10],
                    str(e),
                )

        # Step 5: Calculate full performance metrics for enriched picks
        logger.info(f"Calculating performance metrics for {len(enriched_picks)} qualified wallets...")
        top_5_performance = []

        for pick in enriched_picks:
            wallet = pick["wallet"]
            try:
                positions = wallet_closed_positions.get(wallet, [])
                metrics = self.profiler.calculate_pnl_metrics(positions)

                performance = {
                    "wallet": wallet,
                    "scan_event_id": None,  # Will be set after scan_event is created
                    "market_id": market.market_id,
                    "side": pick["side"],
                    "entry_price": pick["entry_price"],
                    "size": pick["size"],
                    "value": pick["value"],
                    "rank_score": pick["rank_score"],
                    "copyability_score": pick["copyability_score"],
                    # Performance metrics (from history used in pipeline)
                    "total_profits": metrics["total_profits"],
                    "total_losses": metrics["total_losses"],
                    "profit_factor": metrics["profit_factor"],
                    "num_wins": metrics["num_wins"],
                    "num_losses": metrics["num_losses"],
                    "avg_win": metrics["avg_win"],
                    "avg_loss": metrics["avg_loss"],
                    "best_trade": metrics["best_trade"],
                    "worst_trade": metrics["worst_trade"],
                    "best_trade_timestamp": metrics["best_trade_timestamp"],
                    "worst_trade_timestamp": metrics["worst_trade_timestamp"],
                    # Streak metrics — FIX: was missing, causing columns to show 0
                    "best_perf_amount": metrics["best_perf_amount"],
                    "best_perf_count": metrics["best_perf_count"],
                    "worst_perf_amount": metrics["worst_perf_amount"],
                    "worst_perf_count": metrics["worst_perf_count"],
                    "total_positions": metrics["total_positions"],
                    "avg_trade_size": metrics["avg_trade_size"],
                    # Pipeline metrics
                    "roi_4d": pick.get("roi_4d", 0.0),
                    "win_rate_4d": pick.get("win_rate_4d", 0.0),
                }
                top_5_performance.append(performance)
            except Exception as e:
                logger.error(f"Failed to calculate performance for {wallet}: {e}")
                # Still include wallet with partial metrics
                top_5_performance.append({
                    "wallet": wallet,
                    "scan_event_id": None,
                    "market_id": market.market_id,
                    "side": pick["side"],
                    "entry_price": pick["entry_price"],
                    "size": pick["size"],
                    "value": pick["value"],
                    "rank_score": pick["rank_score"],
                    "copyability_score": pick["copyability_score"],
                    "total_profits": 0.0,
                    "total_losses": 0.0,
                    "profit_factor": 0.0,
                    "num_wins": 0,
                    "num_losses": 0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                    "best_trade": 0.0,
                    "worst_trade": 0.0,
                    "best_trade_timestamp": None,
                    "worst_trade_timestamp": None,
                    # Streak metrics — FIX: was missing, causing columns to show 0
                    "best_perf_amount": 0.0,
                    "best_perf_count": 0,
                    "worst_perf_amount": 0.0,
                    "worst_perf_count": 0,
                    "total_positions": 0,
                    "avg_trade_size": 0.0,
                    "roi_4d": pick.get("roi_4d", 0.0),
                    "win_rate_4d": pick.get("win_rate_4d", 0.0),
                })

        logger.info(f"Calculated performance metrics for {len(top_5_performance)} wallets")

        # Step 6: Save to database
        scan_event_id = self.db.create_scan_event(market.market_id, trigger_ts, progress_pct)

        # Update scan_event_id in performance data
        for perf in top_5_performance:
            perf["scan_event_id"] = scan_event_id

        # Save positions
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
                for p in enriched_picks
            ],
        )

        # Save top wallet picks
        self.db.save_top_wallet_picks(scan_event_id, enriched_picks, market.timeframe)

        # Save performance metrics for top 5 wallets
        self.db.save_top_wallet_performance(top_5_performance)
        logger.info(f"Saved performance metrics for top {len(top_5_performance)} wallets")

        # Update unified dashboard summary table for optimized retrieval
        for perf in top_5_performance:
            # Get position history for this wallet (scanner observations)
            positions = self.db.conn.execute(
                """SELECT mp.*, se.trigger_ts
                   FROM market_positions mp
                   JOIN scan_events se ON mp.scan_event_id = se.id
                   WHERE mp.wallet = ?
                   ORDER BY se.trigger_ts DESC""",
                (perf["wallet"],)
            ).fetchall()

            # Use cached closed positions for accurate hold time calculation
            closed_positions = wallet_closed_positions.get(perf["wallet"], [])
            if closed_positions:
                avg_hold_time = self.profiler.calculate_avg_time_between_closed_positions(closed_positions)
            else:
                avg_hold_time = 300  # Default 5 minutes fallback

            # Calculate metrics from scanner positions
            recent_position = positions[0] if positions else None
            profit_24h = sum(p["value"] for p in positions if p["trigger_ts"] >= (trigger_ts - 86400))
            avg_time_between = self._calculate_avg_time_between([dict(p) for p in positions])

            # Calculate win rate from closed positions
            total_closed = perf["total_positions"]
            win_rate_from_closed = (perf["num_wins"] / total_closed * 100) if total_closed > 0 else 0

            # Calculate avg trades per day from closed positions
            avg_trades_per_day_from_closed = total_closed / self.filter_pipeline.lookback_days if total_closed > 0 else 0

            dashboard_data = {
                "wallet": perf["wallet"],
                "scan_event_id": scan_event_id,

                # Recent activity
                "profit_24h": profit_24h,
                "recent_trade_market": market.title if recent_position else None,
                "recent_trade_side": recent_position["side"] if recent_position else None,
                "recent_trade_timestamp": recent_position["trigger_ts"] if recent_position else None,
                "recent_trade_pnl": recent_position["value"] * 0.05 if recent_position else None,  # Estimate
                "avg_time_between_positions": avg_time_between,
                "last_position_timestamp": recent_position["trigger_ts"] if recent_position else None,

                # Track record - from history used in pipeline
                "win_rate": win_rate_from_closed,
                "total_trades": total_closed,
                "avg_trades_per_day": avg_trades_per_day_from_closed,
                "avg_hold_time_seconds": avg_hold_time,
                "avg_trade_size": perf["avg_trade_size"],

                # Performance metrics from closed positions
                "total_profits": perf["total_profits"],
                "total_losses": perf["total_losses"],
                "profit_factor": perf["profit_factor"],
                "num_wins": perf["num_wins"],
                "num_losses": perf["num_losses"],
                "avg_win": perf["avg_win"],
                "avg_loss": perf["avg_loss"],
                "best_trade_amount": perf["best_trade"],
                "best_trade_time_ago": perf["best_trade_timestamp"],
                "worst_trade_amount": perf["worst_trade"],
                "worst_trade_time_ago": perf["worst_trade_timestamp"],
                # Streak metrics — FIX: was missing from dashboard_data, causing columns to show 0
                "best_perf_amount": perf["best_perf_amount"],
                "best_perf_count": perf["best_perf_count"],
                "worst_perf_amount": perf["worst_perf_amount"],
                "worst_perf_count": perf["worst_perf_count"],
            }

            self.db.upsert_wallet_dashboard_summary(dashboard_data)

        logger.info(f"Updated dashboard summary for {len(top_5_performance)} wallets")

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
                    "roi_7d": p.get("roi_4d", 0.0),
                    "win_rate_7d": p.get("win_rate_4d", 0.0),
                    "copyability_score": p.get("copyability_score", 0.0),
                }
                for p in enriched_picks
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

    def _calculate_avg_time_between(self, positions: list[dict]) -> int:
        """Calculate average time between positions"""
        if len(positions) < 2:
            return 0
        timestamps = sorted([p["trigger_ts"] for p in positions])
        intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        return int(sum(intervals) / len(intervals)) if intervals else 0

    def _calculate_avg_hold_time(self, positions: list[dict]) -> int:
        """Calculate average hold time (simplified estimate)"""
        # Group by market and calculate time between first and last position
        from collections import defaultdict
        by_market = defaultdict(list)
        for p in positions:
            by_market[p.get("market_id", "unknown")].append(p["trigger_ts"])

        hold_times = []
        for market_positions in by_market.values():
            if len(market_positions) >= 2:
                market_positions.sort()
                hold_times.append(market_positions[-1] - market_positions[0])

        return int(sum(hold_times) / len(hold_times)) if hold_times else 300


def main() -> None:
    validate_config()
    # Ensure tracker db parent dir exists.
    os.makedirs(os.path.dirname(TRACKER_DATABASE_PATH), exist_ok=True)
    tracker = BTCMarketTracker()
    print("Tracker is running. Waiting for market scans... (Ctrl+C to stop)")
    asyncio.run(tracker.run_forever())


if __name__ == "__main__":
    main()

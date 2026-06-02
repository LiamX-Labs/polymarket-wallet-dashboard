"""
Sequential Wallet Filter Pipeline for Polymarket

Implements 4-stage filtering:
1. Minimum Profit Filter: Total Profit > $1
2. Hold Time Filter: Average hold time >= 10 minutes (anti-bot)
3. Trade Volume Filter: Total closed trades >= 20 (statistical significance)
4. Performance Alpha Filter: Win rate > 40% AND average return > 100%
"""

import logging
from datetime import datetime, timedelta
from typing import Iterable, List, Dict, Tuple, Optional
import concurrent.futures

if __package__ in {None, ""}:
    from polymarket_api_fetcher import PolymarketAPIFetcher
    from wallet_profiler import WalletProfiler
else:
    from .polymarket_api_fetcher import PolymarketAPIFetcher
    from .wallet_profiler import WalletProfiler

logger = logging.getLogger(__name__)


class WalletFilterPipeline:
    """Sequential filtering pipeline for discovering high-quality wallets."""

    # Filter thresholds (configurable via init)
    DEFAULT_LOOKBACK_DAYS = 4
    DEFAULT_MIN_PROFIT = 1.0
    DEFAULT_MIN_HOLD_TIME_MINUTES = 3
    DEFAULT_MIN_TRADE_COUNT = 10
    DEFAULT_MIN_WIN_RATE = 40.0
    DEFAULT_MIN_AVG_RETURN = 70.0
    MAX_WORKERS = 5  # Reduced from 10 to avoid 429 rate limits

    def __init__(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        min_profit: float = DEFAULT_MIN_PROFIT,
        min_hold_time_minutes: float = DEFAULT_MIN_HOLD_TIME_MINUTES,
        min_trade_count: int = DEFAULT_MIN_TRADE_COUNT,
        min_win_rate: float = DEFAULT_MIN_WIN_RATE,
        min_avg_return: float = DEFAULT_MIN_AVG_RETURN,
    ):
        self.fetcher = PolymarketAPIFetcher()
        self.profiler = WalletProfiler()
        
        self.lookback_days = lookback_days
        self.min_profit = min_profit
        self.min_hold_time_minutes = min_hold_time_minutes
        self.min_trade_count = min_trade_count
        self.min_win_rate = min_win_rate
        self.min_avg_return = min_avg_return

    def run_pipeline(self, candidate_wallets: Iterable[str], market_title: str = None) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
        """
        Run the complete 4-stage filter pipeline on candidate wallets.

        Args:
            candidate_wallets: List of wallet addresses to filter
            market_title: Optional market title for logging

        Returns:
            Tuple of (qualified_wallets_list, wallet_data_cache_dict)
        """
        context = {
            "market": market_title or "BTC Markets",
        }
        
        # Convert to list and remove duplicates
        wallets = list(set(candidate_wallets))
        context["initial_count"] = len(wallets)
        
        logger.info(
            "Pipeline START | market=%s initial_wallets=%s lookback=%sd",
            context["market"],
            context["initial_count"],
            self.lookback_days,
        )

        if not wallets:
            return [], {}

        # Step 0: Fetch data for all wallets in parallel
        cutoff_timestamp = int(
            (datetime.utcnow() - timedelta(days=self.lookback_days)).timestamp()
        )
        wallet_data = self._fetch_all_wallets_parallel(wallets, cutoff_timestamp)

        # Stage 1: Minimum Profit Filter
        stage1_wallets = self._filter_by_minimum_profit(wallets, wallet_data)
        logger.info(
            "Pipeline Stage 1: Profit Filter | threshold=$%.2f "
            "passed=%s filtered_out=%s",
            self.min_profit,
            len(stage1_wallets),
            len(wallets) - len(stage1_wallets),
        )

        # Early exit if no wallets pass stage 1
        if not stage1_wallets:
            logger.warning("Pipeline STOPPED at Stage 1: No wallets with profit > $%.2f", self.min_profit)
            return [], wallet_data

        # Stage 2: Hold Time Filter (Anti-Bot/Scalper)
        stage2_wallets = self._filter_by_hold_time(stage1_wallets, wallet_data)
        logger.info(
            "Pipeline Stage 2: Hold Time Filter | threshold=%d min "
            "passed=%s filtered_out=%s",
            self.min_hold_time_minutes,
            len(stage2_wallets),
            len(stage1_wallets) - len(stage2_wallets),
        )

        # Early exit if no wallets pass stage 2
        if not stage2_wallets:
            logger.warning(
                "Pipeline STOPPED at Stage 2: No wallets with avg hold time >= %d minutes",
                self.min_hold_time_minutes,
            )
            return [], wallet_data

        # Stage 3: Trade Volume Filter (Statistical Significance)
        stage3_wallets = self._filter_by_trade_count(stage2_wallets, wallet_data)
        logger.info(
            "Pipeline Stage 3: Trade Volume Filter | threshold=%d trades "
            "passed=%s filtered_out=%s",
            self.min_trade_count,
            len(stage3_wallets),
            len(stage2_wallets) - len(stage3_wallets),
        )

        # Early exit if no wallets pass stage 3
        if not stage3_wallets:
            logger.warning(
                "Pipeline STOPPED at Stage 3: No wallets with >= %d closed trades",
                self.min_trade_count,
            )
            return [], wallet_data

        # Stage 4: Performance Alpha Filter
        qualified_wallets = self._filter_by_performance_alpha(stage3_wallets, wallet_data)
        logger.info(
            "Pipeline Stage 4: Performance Alpha Filter | win_rate>%.0f%% avg_return>%.0f%% "
            "passed=%s filtered_out=%s",
            self.min_win_rate,
            self.min_avg_return,
            len(qualified_wallets),
            len(stage3_wallets) - len(qualified_wallets),
        )

        # Sort by ROI (descending) for final ranking
        qualified_wallets.sort(key=lambda x: x.get("roi", 0), reverse=True)

        logger.info(
            "Pipeline COMPLETE | market=%s qualified=%s "
            "stage1=%s→stage2=%s→stage3=%s→stage4=%s",
            context["market"],
            len(qualified_wallets),
            len(stage1_wallets),
            len(stage2_wallets),
            len(stage3_wallets),
            len(qualified_wallets),
        )

        return qualified_wallets, wallet_data

    def _fetch_all_wallets_parallel(self, wallets: List[str], cutoff_timestamp: int) -> Dict[str, List[Dict]]:
        """Fetch all wallet data in parallel."""
        wallet_to_positions = {}
        
        logger.info("Fetching data for %d wallets in parallel (max_workers=%d)...", len(wallets), self.MAX_WORKERS)
        start_time = datetime.utcnow()

        def fetch_one(wallet: str) -> Tuple[str, List[Dict]]:
            try:
                positions = self.fetcher.get_all_closed_positions(
                    wallet, cutoff_timestamp=cutoff_timestamp
                )
                return wallet, positions
            except Exception as e:
                logger.debug("Error fetching wallet %s: %s", wallet[:8], e)
                return wallet, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_wallet = {executor.submit(fetch_one, w): w for w in wallets}
            for future in concurrent.futures.as_completed(future_to_wallet):
                wallet, positions = future.result()
                wallet_to_positions[wallet] = positions

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info("Parallel fetch complete | total_wallets=%d elapsed=%.2fs", len(wallets), elapsed)
        return wallet_to_positions

    def _filter_by_minimum_profit(self, wallets: List[str], wallet_data: Dict[str, List[Dict]]) -> List[str]:
        """Filter 1: Keep wallets with total profit > min_profit threshold."""
        passed = []
        for wallet in wallets:
            positions = wallet_data.get(wallet, [])
            if not positions:
                continue
            total_pnl = sum(float(p.get("realizedPnl", 0) or 0) for p in positions)
            if total_pnl > self.min_profit:
                passed.append(wallet)
        return passed

    def _filter_by_hold_time(self, wallets: List[str], wallet_data: Dict[str, List[Dict]]) -> List[str]:
        """Filter 2: Keep wallets with average hold time >= min_hold_time_minutes."""
        passed = []
        for wallet in wallets:
            positions = wallet_data.get(wallet, [])
            if len(positions) < 2:
                continue
            avg_hold_time_seconds = self.profiler.calculate_avg_time_between_closed_positions(positions)
            avg_hold_time_minutes = avg_hold_time_seconds / 60.0
            if avg_hold_time_minutes >= self.min_hold_time_minutes:
                passed.append(wallet)
        return passed

    def _filter_by_trade_count(self, wallets: List[str], wallet_data: Dict[str, List[Dict]]) -> List[str]:
        """Filter 3: Keep wallets with total closed trades >= min_trade_count."""
        passed = []
        for wallet in wallets:
            positions = wallet_data.get(wallet, [])
            if len(positions) >= self.min_trade_count:
                passed.append(wallet)
        return passed

    def _filter_by_performance_alpha(self, wallets: List[str], wallet_data: Dict[str, List[Dict]]) -> List[Dict]:
        """Filter 4: Win rate > min_win_rate AND average return per trade > min_avg_return."""
        qualified = []
        for wallet in wallets:
            positions = wallet_data.get(wallet, [])
            if not positions:
                continue
            pnl_metrics = self.profiler.calculate_pnl_metrics(positions)
            win_rate = pnl_metrics.get("win_rate", 0.0)
            avg_return_per_trade = pnl_metrics.get("avg_return_per_trade", 0.0)
            
            # Use net PnL (profits - losses) for reporting
            total_pnl = pnl_metrics.get("total_profits", 0.0) - pnl_metrics.get("total_losses", 0.0)
            num_trades = pnl_metrics.get("total_positions", 0)
            
            if win_rate > self.min_win_rate and avg_return_per_trade > self.min_avg_return:
                qualified.append({
                    "wallet": wallet,
                    "win_rate": win_rate,
                    "avg_return_per_trade": avg_return_per_trade,
                    "total_pnl": total_pnl,
                    "num_trades": num_trades,
                    "roi": avg_return_per_trade,
                })
        return qualified

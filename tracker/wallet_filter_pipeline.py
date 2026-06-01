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
from typing import Iterable, List, Dict, Tuple

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
    DEFAULT_MIN_HOLD_TIME_MINUTES = 10
    DEFAULT_MIN_TRADE_COUNT = 20
    DEFAULT_MIN_WIN_RATE = 40.0
    DEFAULT_MIN_AVG_RETURN = 100.0

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

    def run_pipeline(self, candidate_wallets: Iterable[str], market_title: str = None) -> List[Dict]:
        """
        Run the complete 4-stage filter pipeline on candidate wallets.

        Args:
            candidate_wallets: List of wallet addresses to filter
            market_title: Optional market title for logging

        Returns:
            List of qualifying wallets with their metrics, sorted by ROI (descending)
        """
        context = {
            "market": market_title or "BTC Markets",
            "initial_count": len(list(candidate_wallets)),
        }
        
        # Convert to list if needed
        wallets = list(set(candidate_wallets))  # Remove duplicates
        context["initial_count"] = len(wallets)
        
        logger.info(
            "Pipeline START | market=%s initial_wallets=%s lookback=%sd",
            context["market"],
            context["initial_count"],
            self.lookback_days,
        )

        # Stage 1: Minimum Profit Filter
        stage1_wallets = self._filter_by_minimum_profit(wallets)
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
            return []

        # Stage 2: Hold Time Filter (Anti-Bot/Scalper)
        stage2_wallets = self._filter_by_hold_time(stage1_wallets)
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
            return []

        # Stage 3: Trade Volume Filter (Statistical Significance)
        stage3_wallets = self._filter_by_trade_count(stage2_wallets)
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
            return []

        # Stage 4: Performance Alpha Filter
        qualified_wallets = self._filter_by_performance_alpha(stage3_wallets)
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

        return qualified_wallets

    def _filter_by_minimum_profit(self, wallets: List[str]) -> List[str]:
        """
        Filter 1: Keep wallets with total profit > min_profit threshold.

        Returns:
            List of wallet addresses that passed the filter
        """
        cutoff_timestamp = int(
            (datetime.utcnow() - timedelta(days=self.lookback_days)).timestamp()
        )
        passed = []

        for wallet in wallets:
            try:
                positions = self.fetcher.get_all_closed_positions(
                    wallet, cutoff_timestamp=cutoff_timestamp
                )
                if not positions:
                    continue

                total_pnl = sum(float(p.get("realizedPnl", 0) or 0) for p in positions)

                if total_pnl > self.min_profit:
                    passed.append(wallet)
            except Exception as e:
                logger.debug("Error fetching positions for wallet %s: %s", wallet[:10], str(e))

        return passed

    def _filter_by_hold_time(self, wallets: List[str]) -> List[str]:
        """
        Filter 2: Keep wallets with average hold time >= min_hold_time_minutes.

        Hold time = (position close timestamp - position close timestamp of previous) / position count
        This filters out HFT/scalper bots that flip positions too quickly.

        Returns:
            List of wallet addresses that passed the filter
        """
        cutoff_timestamp = int(
            (datetime.utcnow() - timedelta(days=self.lookback_days)).timestamp()
        )
        passed = []

        for wallet in wallets:
            try:
                positions = self.fetcher.get_all_closed_positions(
                    wallet, cutoff_timestamp=cutoff_timestamp
                )
                if len(positions) < 2:  # Need at least 2 positions to measure hold time
                    continue

                avg_hold_time_seconds = self.profiler.calculate_avg_time_between_closed_positions(
                    positions
                )
                avg_hold_time_minutes = avg_hold_time_seconds / 60.0

                if avg_hold_time_minutes >= self.min_hold_time_minutes:
                    passed.append(wallet)
            except Exception as e:
                logger.debug("Error checking hold time for wallet %s: %s", wallet[:10], str(e))

        return passed

    def _filter_by_trade_count(self, wallets: List[str]) -> List[str]:
        """
        Filter 3: Keep wallets with total closed trades >= min_trade_count.

        This ensures statistical significance and filters out lucky one-off trades.

        Returns:
            List of wallet addresses that passed the filter
        """
        cutoff_timestamp = int(
            (datetime.utcnow() - timedelta(days=self.lookback_days)).timestamp()
        )
        passed = []

        for wallet in wallets:
            try:
                positions = self.fetcher.get_all_closed_positions(
                    wallet, cutoff_timestamp=cutoff_timestamp
                )
                if len(positions) >= self.min_trade_count:
                    passed.append(wallet)
            except Exception as e:
                logger.debug("Error counting trades for wallet %s: %s", wallet[:10], str(e))

        return passed

    def _filter_by_performance_alpha(self, wallets: List[str]) -> List[Dict]:
        """
        Filter 4: Keep wallets meeting BOTH criteria:
        - Win rate > min_win_rate (default 70%)
        - Average return per trade > min_avg_return (default 100%)

        Returns:
            List of dicts with wallet address and performance metrics
        """
        cutoff_timestamp = int(
            (datetime.utcnow() - timedelta(days=self.lookback_days)).timestamp()
        )
        qualified = []

        for wallet in wallets:
            try:
                positions = self.fetcher.get_all_closed_positions(
                    wallet, cutoff_timestamp=cutoff_timestamp
                )
                if not positions:
                    continue

                # Calculate performance metrics
                pnl_metrics = self.profiler.calculate_pnl_metrics(positions)
                win_rate = pnl_metrics.get("win_rate", 0.0)  # Already in percentage
                total_pnl = pnl_metrics.get("total_profits", 0.0)
                num_trades = pnl_metrics.get("total_positions", 0)

                # Calculate average return per trade
                if num_trades > 0:
                    avg_return_per_trade = (total_pnl / num_trades) * 100.0  # Convert to percentage
                else:
                    avg_return_per_trade = 0.0

                # Check both criteria
                if win_rate > self.min_win_rate and avg_return_per_trade > self.min_avg_return:
                    qualified.append(
                        {
                            "wallet": wallet,
                            "win_rate": win_rate,
                            "avg_return_per_trade": avg_return_per_trade,
                            "total_pnl": total_pnl,
                            "num_trades": num_trades,
                            "roi": (total_pnl / num_trades) * 100.0 if num_trades > 0 else 0.0,
                        }
                    )
            except Exception as e:
                logger.debug("Error calculating performance for wallet %s: %s", wallet[:10], str(e))

        return qualified

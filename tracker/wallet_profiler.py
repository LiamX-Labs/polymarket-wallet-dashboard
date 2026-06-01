from datetime import datetime, timedelta
from statistics import median
from typing import Iterable
import os
import signal
import logging
from contextlib import contextmanager

if __package__ in {None, ""}:
    from polymarket_api_fetcher import PolymarketAPIFetcher
    from wallet_analyzer import WalletAnalyzer
else:
    from .polymarket_api_fetcher import PolymarketAPIFetcher
    from .wallet_analyzer import WalletAnalyzer

from bot.config import POLYGONSCAN_API_KEY

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Exception raised when operation times out."""
    pass


@contextmanager
def timeout(seconds):
    """Context manager for timing out operations."""
    def timeout_handler(signum, frame):
        raise TimeoutException("Operation timed out")

    # Set the signal handler and alarm
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        # Disable the alarm and restore the old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class WalletProfiler:
    """Compute 7d/30d wallet performance and ranking metrics."""

    def __init__(self):
        self.fetcher = PolymarketAPIFetcher()
        # Initialize wallet analyzer for balance lookups (optional - only if API key available)
        self.wallet_analyzer = WalletAnalyzer(api_key=POLYGONSCAN_API_KEY) if POLYGONSCAN_API_KEY else None
        self._balance_cache = {}  # Cache wallet balances to avoid repeated API calls

    def hft_prefilter_4h(self, wallets: Iterable[str]) -> list[dict]:
        """
        Quick HFT check using 4-hour window.
        Returns list of dicts with wallet and hft_flag.
        Only fetches minimal data for fast filtering.
        """
        cutoff = int((datetime.utcnow() - timedelta(hours=4)).timestamp())
        results = []
        for wallet in set(wallets):
            try:
                # Fetch only recent positions for HFT detection
                positions = self.fetcher.get_closed_positions(wallet, limit=50, offset=0, sort_by="TIMESTAMP", sort_direction="DESC")
                if positions:
                    # Filter to 4h window
                    recent = [p for p in positions if p.get('timestamp', 0) >= cutoff]
                    hft_flag = self.is_hft_from_positions(recent) if len(recent) >= 3 else False
                else:
                    hft_flag = False
            except Exception:
                hft_flag = False

            results.append({"wallet": wallet, "hft_flag": hft_flag})
        return results

    def profile_7d(self, wallets: Iterable[str], condition_id: str = None) -> list[dict]:
        """
        Profile wallets based on their 7-day performance.

        Args:
            wallets: List of wallet addresses to profile
            condition_id: Optional conditionId to filter positions to a specific market
        """
        cutoff = int((datetime.utcnow() - timedelta(days=7)).timestamp())
        results = []
        for wallet in set(wallets):
            positions = self.fetcher.get_all_closed_positions(wallet, cutoff_timestamp=cutoff)

            # Filter positions to BTC updown markets only
            # BTC updown market titles contain "Bitcoin" or "BTC"
            btc_positions = [
                p for p in positions
                if 'bitcoin' in (p.get('title') or '').lower() or 'btc' in (p.get('title') or '').lower()
            ]

            # Skip wallets with no BTC updown activity in the 7-day window
            if not btc_positions:
                continue

            # Further filter to specific market if condition_id provided
            if condition_id:
                btc_positions = [p for p in btc_positions if p.get('conditionId') == condition_id]

            # Also fetch trades to get fill counts per position
            trades = self.fetcher.get_all_trades(wallet, cutoff_timestamp=cutoff)
            # Filter trades to BTC markets
            btc_trades = [
                t for t in trades
                if 'bitcoin' in (t.get('title') or '').lower() or 'btc' in (t.get('title') or '').lower()
            ]
            # Filter trades to same market if condition_id provided
            if condition_id:
                btc_trades = [t for t in btc_trades if t.get('conditionId') == condition_id]

            stat = self._compute_stats(wallet, btc_positions, btc_trades)
            results.append(stat)
        return results

    def profile_30d(self, wallets: Iterable[str]) -> list[dict]:
        cutoff = int((datetime.utcnow() - timedelta(days=30)).timestamp())
        results = []
        for wallet in set(wallets):
            positions = self.fetcher.get_all_closed_positions(wallet, cutoff_timestamp=cutoff)
            trades = self.fetcher.get_all_trades(wallet, cutoff_timestamp=cutoff)
            stat = self._compute_stats(wallet, positions, trades)
            stat["specialization"] = self._specialization_from_positions(positions)
            results.append(stat)
        return results

    def get_all_positions_7d(self, wallet: str) -> list[dict]:
        """
        Fetch ALL closed positions (all markets) for a wallet in the last 7 days.
        Returns list of position dictionaries from Polymarket API.
        """
        cutoff = int((datetime.utcnow() - timedelta(days=7)).timestamp())
        return self.fetcher.get_all_closed_positions(wallet, cutoff_timestamp=cutoff)

    def calculate_pnl_metrics(self, positions: list[dict]) -> dict:
        """
        Calculate detailed P&L metrics from closed positions.

        Returns:
            dict with keys:
                - total_profits: sum of all winning positions
                - total_losses: absolute value of sum of all losing positions
                - profit_factor: total_profits / total_losses
                - num_wins: count of winning positions
                - num_losses: count of losing positions
                - avg_win: average profit per winning position
                - avg_loss: average loss per losing position
                - best_trade: largest single winning position
                - worst_trade: largest single losing position
                - best_trade_timestamp: timestamp of best trade
                - worst_trade_timestamp: timestamp of worst trade
                - total_positions: total count of closed positions
                - avg_return_per_trade: average ROI per trade (percentage)
        """
        if not positions:
            return {
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
                "total_positions": 0,
                "avg_return_per_trade": 0.0,
            }

        # Create list of (pnl, timestamp) tuples
        pnl_data = [(float(p.get("realizedPnl", 0) or 0), int(p.get("timestamp", 0) or 0)) for p in positions]

        # Calculate individual returns for average return per trade
        individual_returns = []
        for p in positions:
            pnl = float(p.get("realizedPnl", 0) or 0)
            avg_price = float(p.get("avgPrice", 0) or 0)
            total_bought = float(p.get("totalBought", 0) or 0)
            capital = avg_price * total_bought
            if capital > 0:
                individual_returns.append(pnl / capital)

        avg_return_per_trade = (sum(individual_returns) / len(individual_returns) * 100.0) if individual_returns else 0.0

        winning_positions = [(pnl, ts) for pnl, ts in pnl_data if pnl > 0]
        losing_positions = [(pnl, ts) for pnl, ts in pnl_data if pnl < 0]

        total_profits = sum(pnl for pnl, _ in winning_positions) if winning_positions else 0.0
        total_losses = abs(sum(pnl for pnl, _ in losing_positions)) if losing_positions else 0.0

        profit_factor = (total_profits / total_losses) if total_losses > 0 else 0.0

        num_wins = len(winning_positions)
        num_losses = len(losing_positions)

        avg_win = (total_profits / num_wins) if num_wins > 0 else 0.0
        avg_loss = (total_losses / num_losses) if num_losses > 0 else 0.0

        # Find best and worst trades with their timestamps
        best_trade_data = max(winning_positions, key=lambda x: x[0]) if winning_positions else (0.0, None)
        worst_trade_data = min(losing_positions, key=lambda x: x[0]) if losing_positions else (0.0, None)

        return {
            "total_profits": total_profits,
            "total_losses": total_losses,
            "profit_factor": profit_factor,
            "num_wins": num_wins,
            "num_losses": num_losses,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "best_trade": best_trade_data[0],
            "worst_trade": worst_trade_data[0],
            "best_trade_timestamp": best_trade_data[1],
            "worst_trade_timestamp": worst_trade_data[1],
            "total_positions": len(positions),
            "avg_return_per_trade": avg_return_per_trade,
        }

    def calculate_avg_time_between_closed_positions(self, positions: list[dict]) -> int:
        """
        Calculate average time between closed positions.

        This measures how long it takes on average before the next position is closed,
        giving insight into trading frequency.

        Args:
            positions: List of closed position dictionaries from Polymarket API

        Returns:
            Average time in seconds between closed positions, or 0 if < 2 positions
        """
        if len(positions) < 2:
            return 0

        # Extract timestamps and sort them
        timestamps = sorted([int(p.get("timestamp", 0) or 0) for p in positions if p.get("timestamp")])

        if len(timestamps) < 2:
            return 0

        # Calculate intervals between consecutive closed positions
        intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]

        # Return average interval in seconds
        return int(sum(intervals) / len(intervals)) if intervals else 0

    @staticmethod
    def rank_score(wallet_stat: dict) -> float:
        # Heavily weighted toward ROI, with minor bonuses for win rate and trade count.
        # ROI is the primary signal (95% weight), other factors provide small adjustments.
        count_factor = min(1.0, wallet_stat["trade_count"] / 20.0)
        return (
            wallet_stat["roi"] * 0.95
            + wallet_stat["win_rate"] * 0.03
            + count_factor * 2.0
        )

    @staticmethod
    def copyability_score(position_first_seen_ts: int, trigger_ts: int, size: float, hft_flag: bool) -> float:
        lead_minutes = max(0.0, (trigger_ts - position_first_seen_ts) / 60.0) if position_first_seen_ts else 0.0
        lead_component = min(50.0, lead_minutes * 2.0)
        size_component = min(40.0, size / 100.0)
        penalty = 50.0 if hft_flag else 0.0
        return max(0.0, lead_component + size_component + 10.0 - penalty)

    @staticmethod
    def is_hft_from_positions(positions: list[dict]) -> bool:
        timestamps = sorted(p.get("timestamp", 0) for p in positions if p.get("timestamp"))
        if len(timestamps) < 3:
            return False

        hours = {}
        for ts in timestamps:
            hour_bucket = int(ts // 3600)
            hours[hour_bucket] = hours.get(hour_bucket, 0) + 1

        avg_positions_per_hour = sum(hours.values()) / max(1, len(hours))
        diffs_minutes = [(timestamps[i] - timestamps[i - 1]) / 60.0 for i in range(1, len(timestamps))]
        median_between = median(diffs_minutes) if diffs_minutes else 0.0
        return median_between < 5.0 and avg_positions_per_hour > 10.0

    def _compute_stats(self, wallet: str, positions: list[dict], trades: list[dict] = None) -> dict:
        if not positions:
            return {
                "wallet": wallet,
                "roi": 0.0,
                "win_rate": 0.0,
                "pnl": 0.0,
                "trade_count": 0,
                "fill_count": 0,
                "avg_trade_size": 0.0,
                "total_capital_invested": 0.0,
                "estimated_bankroll": 0.0,
                "hft_flag": False,
            }

        pnl_values = [float(p.get("realizedPnl", 0) or 0) for p in positions]
        sizes = [float(p.get("totalBought", 0) or 0) for p in positions]

        # Calculate capital per position and track timing for concurrent positions
        position_data = []
        for p in positions:
            avg_price = float(p.get("avgPrice", 0) or 0)
            total_bought = float(p.get("totalBought", 0) or 0)
            capital = avg_price * total_bought
            timestamp = int(p.get("timestamp", 0) or 0)
            position_data.append({
                "capital": capital,
                "timestamp": timestamp,
            })

        # Try to get real wallet bankroll from PolygonScan (net deposits)
        real_bankroll = self._get_wallet_bankroll(wallet)

        # If real bankroll unavailable, estimate from position data
        estimated_bankroll = self._estimate_bankroll(position_data)

        # Use real bankroll if available and non-zero, otherwise use estimate
        bankroll = real_bankroll if real_bankroll > 0 else estimated_bankroll

        # Count fills (trades) per position
        fill_count = 0
        if trades:
            # Map trades to positions using conditionId + outcome
            for trade in trades:
                condition_id = trade.get('conditionId', '')
                outcome = trade.get('outcome', '')
                # Count fills for positions that exist in our closed positions
                for pos in positions:
                    if pos.get('conditionId') == condition_id and pos.get('outcome') == outcome:
                        fill_count += 1
                        break
        else:
            # Fallback: use position count if no trades data
            fill_count = len(positions)

        total_pnl = sum(pnl_values)
        total_size = sum(sizes) or 1.0
        total_capital = sum(p["capital"] for p in position_data) or 1.0

        # ROI based on actual wallet bankroll (net deposits from PolygonScan)
        # This is Portfolio ROI
        roi = (total_pnl / bankroll) * 100.0 if bankroll > 0 else 0.0
        
        # Get detailed PnL metrics for win rate and average return per trade
        pnl_metrics = self.calculate_pnl_metrics(positions)
        win_rate = pnl_metrics.get("win_rate", 0.0)
        avg_return_per_trade = pnl_metrics.get("avg_return_per_trade", 0.0)

        return {
            "wallet": wallet,
            "roi": roi,
            "win_rate": win_rate,
            "pnl": total_pnl,
            "avg_return_per_trade": avg_return_per_trade,
            "trade_count": len(pnl_values),
            "fill_count": fill_count,
            "avg_trade_size": total_size / len(sizes),
            "total_capital_invested": total_capital,
            "estimated_bankroll": estimated_bankroll,
            "real_bankroll": real_bankroll,
            "bankroll": bankroll,  # Actual value used for ROI (real or estimated)
            "hft_flag": self.is_hft_from_positions(positions),
        }

    def _get_wallet_bankroll(self, wallet: str) -> float:
        """
        Get wallet's actual bankroll (net deposits) from PolygonScan.

        Falls back to estimated bankroll if PolygonScan API is unavailable.
        Uses caching to avoid repeated API calls for the same wallet.
        """
        # Check cache first
        if wallet in self._balance_cache:
            return self._balance_cache[wallet]

        # Try to fetch real balance if API available
        if self.wallet_analyzer:
            try:
                # Add 10-second timeout to prevent freezing
                with timeout(10):
                    analysis = self.wallet_analyzer.analyze_wallet(wallet, days_back=30)
                    # net_balance = deposits - withdrawals = actual wallet bankroll
                    bankroll = float(analysis.get('net_balance', 0))

                    # Cache the result
                    self._balance_cache[wallet] = bankroll
                    return bankroll
            except TimeoutException:
                logger.warning("Bankroll fetch timed out for wallet %s, using estimation", wallet[:10])
                # Cache a timeout marker to avoid retrying this wallet
                self._balance_cache[wallet] = 0.0
            except Exception as e:
                logger.debug("Bankroll fetch failed for wallet %s: %s", wallet[:10], str(e))
                # Cache failure to avoid retrying
                self._balance_cache[wallet] = 0.0

        # No API key or API failed - will use estimation
        return 0.0  # Signal to use estimated bankroll

    @staticmethod
    def _estimate_bankroll(position_data: list[dict]) -> float:
        """
        Estimate wallet's trading bankroll by finding peak concurrent capital.

        Uses a simplified approach: take the max of either:
        1. Largest single position (min bankroll needed)
        2. Average of top 3 largest positions (better estimate for active traders)

        This approximates the wallet's actual trading capital without knowing
        exact timing of overlapping positions.
        """
        if not position_data:
            return 0.0

        capitals = sorted([p["capital"] for p in position_data], reverse=True)

        # Max single position (minimum possible bankroll)
        max_single = capitals[0]

        # Average of top 3 positions (assumes some concurrent trading)
        top_3_avg = sum(capitals[:3]) / min(3, len(capitals))

        # Use whichever is larger as bankroll estimate
        # For wallets with few positions, this will be close to max_single
        # For active traders, this better represents their actual bankroll
        return max(max_single, top_3_avg)

    @staticmethod
    def _specialization_from_positions(positions: list[dict]) -> str:
        if not positions:
            return "insufficient_data"
        buckets = {"5m": 0, "15m": 0, "1h": 0, "4h": 0}
        for p in positions:
            title = (p.get("title") or "").lower()
            for tf in buckets:
                if tf in title:
                    buckets[tf] += 1
        best_tf = max(buckets, key=buckets.get)
        if buckets[best_tf] == 0:
            return "mixed"
        return f"{best_tf}_focus"


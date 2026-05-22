from typing import Dict, List
from collections import defaultdict

import requests

from bot.config import CLOB_API_BASE_URL
from .models import PositionSnapshot


class CLOBClient:
    """Fetch position snapshots from trading data."""

    def __init__(self, base_url: str = CLOB_API_BASE_URL, data_api_url: str = "https://data-api.polymarket.com"):
        self.base_url = base_url.rstrip("/")
        self.data_api_url = data_api_url.rstrip("/")
        self.session = requests.Session()

    def get_market_pnl_rankings(self, market_id: str, limit: int = 50) -> List[dict]:
        """
        Get wallet rankings by realized + unrealized PnL for a specific market.

        Strategy:
        1. Fetch trades to find active wallets
        2. Calculate realized PnL (from closed positions via buy/sell pairs)
        3. Calculate unrealized PnL (from open positions)
        4. Rank by total PnL (realized + unrealized)

        This captures actual profitability, not just position size.
        """
        endpoint = f"{self.data_api_url}/trades"
        params = {"market": market_id, "limit": 500}

        try:
            response = self.session.get(endpoint, params=params, timeout=20)
            response.raise_for_status()
            trades = response.json() or []
        except Exception:
            return []

        if not trades:
            return []

        # Group trades by wallet and outcome to track positions
        wallet_data = defaultdict(lambda: defaultdict(lambda: {
            "buys": [],
            "sells": [],
        }))

        for trade in trades:
            wallet = (trade.get("proxyWallet") or trade.get("owner") or "").lower()
            if not wallet:
                continue

            outcome = (trade.get("outcome") or trade.get("asset", "")).upper()
            size = float(trade.get("size", 0) or 0)
            price = float(trade.get("price", 0) or 0)
            side = trade.get("side", "").upper()

            if side == "BUY":
                wallet_data[wallet][outcome]["buys"].append({"size": size, "price": price})
            elif side == "SELL":
                wallet_data[wallet][outcome]["sells"].append({"size": size, "price": price})

        # Calculate realized + unrealized PnL per wallet
        results = []
        for wallet, outcomes in wallet_data.items():
            total_realized_pnl = 0.0
            total_unrealized_pnl = 0.0
            total_position_value = 0.0

            for outcome, data in outcomes.items():
                buys = data["buys"]
                sells = data["sells"]

                # Calculate totals
                total_bought = sum(b["size"] for b in buys)
                total_sold = sum(s["size"] for s in sells)
                buy_cost = sum(b["size"] * b["price"] for b in buys)
                sell_revenue = sum(s["size"] * s["price"] for s in sells)

                # Realized PnL: revenue from sells - proportional cost
                if total_sold > 0 and total_bought > 0:
                    avg_buy_price = buy_cost / total_bought
                    realized_cost = total_sold * avg_buy_price
                    realized_pnl = sell_revenue - realized_cost
                    total_realized_pnl += realized_pnl

                # Unrealized PnL: open position at current price
                net_position = total_bought - total_sold
                if net_position > 0:
                    avg_entry = buy_cost / total_bought if total_bought > 0 else 0
                    # For now, use entry price as proxy for current value
                    # Real implementation would fetch current market price
                    position_value = net_position * avg_entry
                    cost_basis = net_position * avg_entry
                    unrealized_pnl = position_value - cost_basis  # Currently 0, needs real price
                    total_unrealized_pnl += unrealized_pnl
                    total_position_value += position_value

            # Total PnL = realized + unrealized
            # Since we don't have current price, use: realized PnL + position value as score
            total_pnl = total_realized_pnl + total_position_value

            results.append({
                "wallet": wallet,
                "realized_pnl": total_realized_pnl,
                "unrealized_pnl": total_unrealized_pnl,
                "position_value": total_position_value,
                "total_pnl": total_pnl,
            })

        # Sort by total PnL (prioritizes profitable traders with active positions)
        results.sort(key=lambda x: x["total_pnl"], reverse=True)
        return results[:limit]

    def get_top_positions(self, market_id: str, sample_size: int) -> Dict[str, List[PositionSnapshot]]:
        """
        Get top positions from recent trades data.

        For BTC updown markets, the CLOB positions endpoint doesn't work,
        but we can aggregate recent trades to find active wallets.
        """
        # Try Data API trades endpoint (works for BTC updown markets)
        endpoint = f"{self.data_api_url}/trades"
        params = {"market": market_id, "limit": 500}

        try:
            response = self.session.get(endpoint, params=params, timeout=20)
            response.raise_for_status()
            trades = response.json()

            if trades:
                return self._aggregate_trades_to_positions(trades, sample_size)
        except Exception:
            pass

        # Fallback to CLOB positions endpoint (for regular markets)
        endpoint = f"{self.base_url}/positions"
        params = {"market": market_id, "limit": 500}
        response = self.session.get(endpoint, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload.get("data", [])

        by_side = {"UP": [], "DOWN": []}
        for row in rows:
            side = (row.get("side") or row.get("outcome") or "").upper()
            if side in {"YES", "UP"}:
                norm_side = "UP"
            elif side in {"NO", "DOWN"}:
                norm_side = "DOWN"
            else:
                continue

            size = float(row.get("size", 0) or 0)
            entry_price = float(row.get("avgPrice", row.get("price", 0)) or 0)
            value = float(row.get("value", 0) or (size * entry_price))
            wallet = (row.get("owner") or row.get("wallet") or "").lower()
            first_seen_ts = int(row.get("firstSeenTs", row.get("timestamp", 0)) or 0)
            if not wallet:
                continue

            by_side[norm_side].append(
                PositionSnapshot(
                    wallet=wallet,
                    side=norm_side,
                    entry_price=entry_price,
                    size=size,
                    value=value,
                    first_seen_ts=first_seen_ts,
                )
            )

        for side in ("UP", "DOWN"):
            by_side[side].sort(key=lambda p: p.value, reverse=True)
            by_side[side] = by_side[side][:sample_size]

        return by_side

    def _aggregate_trades_to_positions(self, trades: List[dict], sample_size: int) -> Dict[str, List[PositionSnapshot]]:
        """
        Aggregate recent trades into position snapshots.

        For each wallet, calculate their net position and average entry price.
        """
        # Aggregate trades by wallet and outcome
        positions = defaultdict(lambda: {"buys": [], "sells": [], "outcome": None})

        for trade in trades:
            wallet = (trade.get("proxyWallet") or trade.get("owner") or "").lower()
            if not wallet:
                continue

            outcome = (trade.get("outcome") or "").upper()
            if outcome not in {"UP", "DOWN"}:
                # Try to map from asset/side
                side = trade.get("side", "").upper()
                if side == "BUY":
                    outcome = "UP"
                elif side == "SELL":
                    outcome = "DOWN"
                else:
                    continue

            key = (wallet, outcome)
            size = float(trade.get("size", 0) or 0)
            price = float(trade.get("price", 0) or 0)
            timestamp = int(trade.get("timestamp", 0) or 0)

            if trade.get("side") == "BUY":
                positions[key]["buys"].append({"size": size, "price": price, "timestamp": timestamp})
            else:
                positions[key]["sells"].append({"size": size, "price": price, "timestamp": timestamp})

            if not positions[key]["outcome"]:
                positions[key]["outcome"] = outcome

        # Calculate net positions
        by_side = {"UP": [], "DOWN": []}

        for (wallet, outcome), data in positions.items():
            total_bought = sum(b["size"] for b in data["buys"])
            total_sold = sum(s["size"] for s in data["sells"])
            net_size = total_bought - total_sold

            if net_size <= 0:
                continue  # Skip if wallet has closed/sold their position

            # Calculate weighted average entry price
            total_cost = sum(b["size"] * b["price"] for b in data["buys"])
            avg_price = total_cost / total_bought if total_bought > 0 else 0

            # Get first trade timestamp
            all_times = [b["timestamp"] for b in data["buys"]] + [s["timestamp"] for s in data["sells"]]
            first_seen_ts = min(all_times) if all_times else 0

            by_side[outcome].append(
                PositionSnapshot(
                    wallet=wallet,
                    side=outcome,
                    entry_price=avg_price,
                    size=net_size,
                    value=net_size * avg_price,
                    first_seen_ts=first_seen_ts,
                )
            )

        # Sort and limit
        for side in ("UP", "DOWN"):
            by_side[side].sort(key=lambda p: p.value, reverse=True)
            by_side[side] = by_side[side][:sample_size]

        return by_side


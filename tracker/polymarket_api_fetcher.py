#!/usr/bin/env python3
"""
Polymarket API Data Fetcher
Fetches closed positions and trades directly from Polymarket's Data API

Note: The trades endpoint has a maximum offset of 3000, limiting historical
      trade data to approximately the most recent 4000 trades.
"""

import requests
import sys
import csv
import time
from datetime import datetime


class PolymarketAPIFetcher:
    """Fetches trading data from Polymarket's official API"""

    BASE_URL = "https://data-api.polymarket.com"
    REQUEST_DELAY_SECONDS = 0.3  # Delay between requests to avoid rate limiting
    MAX_RETRIES = 3  # Maximum retry attempts for 408/429 errors
    RETRY_DELAY_BASE = 1.0  # Base delay for exponential backoff

    def __init__(self):
        self.session = requests.Session()

    def get_closed_positions(self, wallet_address, limit=50, offset=0, sort_by="REALIZEDPNL", sort_direction="DESC"):
        """
        Fetch closed positions for a user

        Args:
            wallet_address: User's wallet address
            limit: Results per page (max 50)
            offset: Pagination offset
            sort_by: REALIZEDPNL, TITLE, PRICE, AVGPRICE, or TIMESTAMP
            sort_direction: ASC or DESC
        """
        endpoint = f"{self.BASE_URL}/closed-positions"

        params = {
            'user': wallet_address,
            'limit': min(limit, 50),
            'offset': offset,
            'sortBy': sort_by,
            'sortDirection': sort_direction
        }

        # Retry logic with exponential backoff for 408/429 errors
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(endpoint, params=params, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (408, 429):  # Request timeout or rate limit
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)  # Exponential backoff
                        print(f"API rate limit/timeout (HTTP {response.status_code}), retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{self.MAX_RETRIES})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Error fetching closed positions: {response.status_code} (max retries exceeded)")
                        print(f"Response: {response.text}")
                        return None
                else:
                    print(f"Error fetching closed positions: {response.status_code}")
                    print(f"Response: {response.text}")
                    return None
            except requests.exceptions.Timeout:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    print(f"Request timeout, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Error fetching closed positions: Request timeout (max retries exceeded)")
                    return None
        
        return None

    def get_all_closed_positions(self, wallet_address, cutoff_timestamp=None):
        """
        Fetch ALL closed positions with pagination

        Args:
            wallet_address: User's wallet address
            cutoff_timestamp: Optional unix timestamp - stop fetching when data is older than this
        """

        all_positions = []
        offset = 0
        limit = 50

        # If we have a cutoff timestamp, sort by timestamp DESC to get recent data first
        sort_by = "TIMESTAMP" if cutoff_timestamp else "REALIZEDPNL"
        sort_direction = "DESC" if cutoff_timestamp else "DESC"

        print(f"Fetching closed positions from Polymarket API for {wallet_address}...")

        while True:
            positions = self.get_closed_positions(
                wallet_address,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_direction=sort_direction
            )

            if not positions or len(positions) == 0:
                break

            # If cutoff timestamp specified, check if we should stop early
            if cutoff_timestamp:
                filtered_positions = [p for p in positions if p.get('timestamp', 0) >= cutoff_timestamp]
                all_positions.extend(filtered_positions)
                print(f"  Fetched {len(filtered_positions)}/{len(positions)} positions within timeframe (total: {len(all_positions)})")

                # If we got fewer positions than requested, we've gone past the cutoff
                if len(filtered_positions) < len(positions):
                    print(f"  Reached cutoff date - stopping fetch")
                    break
            else:
                all_positions.extend(positions)
                print(f"  Fetched {len(positions)} positions (total: {len(all_positions)})")

            if len(positions) < limit:
                break

            offset += limit
            # Rate limiting: Add delay between requests to avoid 408 timeouts
            time.sleep(self.REQUEST_DELAY_SECONDS)

        print(f"\nTotal closed positions fetched: {len(all_positions)}\n")
        return all_positions

    def get_trades(self, wallet_address, limit=100, offset=0, side=None, taker_only=True):
        """
        Fetch trades for a user

        Args:
            wallet_address: User's wallet address
            limit: Results per page (max 10,000)
            offset: Pagination offset
            side: "BUY" or "SELL" or None for both
            taker_only: Only show taker trades (default True)
        """
        endpoint = f"{self.BASE_URL}/trades"

        params = {
            'user': wallet_address,
            'limit': min(limit, 1000),
            'offset': offset,
            'takerOnly': taker_only
        }

        if side:
            params['side'] = side

        # Retry logic with exponential backoff for 408/429 errors
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(endpoint, params=params, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (408, 429):  # Request timeout or rate limit
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                        print(f"API rate limit/timeout (HTTP {response.status_code}), retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{self.MAX_RETRIES})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Error fetching trades: {response.status_code} (max retries exceeded)")
                        print(f"Response: {response.text}")
                        return None
                else:
                    print(f"Error fetching trades: {response.status_code}")
                    print(f"Response: {response.text}")
                    return None
            except requests.exceptions.Timeout:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    print(f"Request timeout, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Error fetching trades: Request timeout (max retries exceeded)")
                    return None
        
        return None

    def get_all_trades(self, wallet_address, cutoff_timestamp=None):
        """
        Fetch ALL trades with pagination (up to API limit)

        Note: Polymarket API has a max offset of 3000 for trades.
              For wallets with >4000 trades, only the most recent 4000 can be fetched.
              Use a shorter timeframe (days_back) to ensure all recent trades are captured.

        Args:
            wallet_address: User's wallet address
            cutoff_timestamp: Optional unix timestamp - stop fetching when data is older than this
        """

        all_trades = []
        offset = 0
        limit = 1000
        MAX_OFFSET = 3000  # Polymarket API limit

        print(f"Fetching trades from Polymarket API for {wallet_address}...")

        hit_api_limit = False
        stopped_early = False

        while True:
            # Check if we've reached the API offset limit
            if offset >= MAX_OFFSET:
                hit_api_limit = True
                break

            trades = self.get_trades(wallet_address, limit=limit, offset=offset)

            if not trades or len(trades) == 0:
                break

            # If cutoff timestamp specified, filter and check if we should stop early
            if cutoff_timestamp:
                filtered_trades = [t for t in trades if t.get('timestamp', 0) >= cutoff_timestamp]
                all_trades.extend(filtered_trades)
                print(f"  Fetched {len(filtered_trades)}/{len(trades)} trades within timeframe (total: {len(all_trades)})")

                # If we got fewer trades than requested, we've gone past the cutoff
                if len(filtered_trades) < len(trades):
                    print(f"  Reached cutoff date - stopping fetch")
                    stopped_early = True
                    break
            else:
                all_trades.extend(trades)
                print(f"  Fetched {len(trades)} trades (total: {len(all_trades)})")

            if len(trades) < limit:
                break

            offset += limit
            # Rate limiting: Add delay between requests to avoid 408 timeouts
            time.sleep(self.REQUEST_DELAY_SECONDS)

        # Warning if we hit the API limit without a cutoff
        if hit_api_limit:
            print(f"\n{'='*80}")
            print(f"⚠️  WARNING: Reached Polymarket API offset limit ({MAX_OFFSET})")
            print(f"{'='*80}")
            print(f"  Total trades fetched: {len(all_trades)}")
            print(f"  This wallet may have more than {len(all_trades)} trades.")
            print(f"\n  To ensure complete data, specify a shorter timeframe:")
            print(f"    - Run with fewer days back (e.g., 7, 14, or 30 days)")
            print(f"    - This will fetch all trades within that period")
            print(f"{'='*80}\n")
        else:
            print(f"\nTotal trades fetched: {len(all_trades)}")
            if not stopped_early and len(all_trades) > 0:
                oldest_trade = min(all_trades, key=lambda x: x.get('timestamp', 0))
                oldest_date = datetime.fromtimestamp(oldest_trade.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')
                print(f"Oldest trade: {oldest_date}\n")

        return all_trades

    def export_closed_positions_csv(self, positions, wallet_address, trades=None):
        """Export closed positions to CSV"""

        if not positions:
            print("No positions to export")
            return

        # Count trades per (condition ID + outcome) if trades data is available
        # This is important for HFT detection: we need trades per position, not per market
        trade_counts = {}
        if trades:
            for trade in trades:
                condition_id = trade.get('conditionId', '')
                outcome = trade.get('outcome', '')
                # Create unique key for this position (market + outcome)
                position_key = f"{condition_id}:{outcome}"
                trade_counts[position_key] = trade_counts.get(position_key, 0) + 1

        # Save to data directory
        import os
        data_dir = '../data' if os.path.exists('../data') else 'data'
        os.makedirs(data_dir, exist_ok=True)

        filename = f"{data_dir}/polymarket_closed_positions_{wallet_address}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Market Title',
                'Outcome',
                'Condition ID',
                'Realized PnL',
                'Avg Price',
                'Total Bought',
                'Current Price',
                'Trades',
                'Timestamp',
                'Event Slug',
                'End Date'
            ])

            # Data rows
            for pos in positions:
                condition_id = pos.get('conditionId', '')
                outcome = pos.get('outcome', '')
                # Look up trades using the same position key (condition ID + outcome)
                position_key = f"{condition_id}:{outcome}"
                num_trades = trade_counts.get(position_key, 0) if trades else 'N/A'

                writer.writerow([
                    pos.get('title', ''),
                    pos.get('outcome', ''),
                    condition_id,
                    pos.get('realizedPnl', 0),
                    pos.get('avgPrice', 0),
                    pos.get('totalBought', 0),
                    pos.get('curPrice', 0),
                    num_trades,
                    datetime.fromtimestamp(pos.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S') if pos.get('timestamp') else '',
                    pos.get('eventSlug', ''),
                    pos.get('endDate', '')
                ])

        print(f"✓ Exported {len(positions)} closed positions to {filename}")
        return filename

    def export_trades_csv(self, trades, wallet_address):
        """Export trades to CSV"""

        if not trades:
            print("No trades to export")
            return

        # Save to data directory
        import os
        data_dir = '../data' if os.path.exists('../data') else 'data'
        os.makedirs(data_dir, exist_ok=True)

        filename = f"{data_dir}/polymarket_trades_{wallet_address}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Market Title',
                'Outcome',
                'Side',
                'Size',
                'Price',
                'Condition ID',
                'Timestamp',
                'Transaction Hash',
                'Event Slug'
            ])

            # Data rows
            for trade in trades:
                writer.writerow([
                    trade.get('title', ''),
                    trade.get('outcome', ''),
                    trade.get('side', ''),
                    trade.get('size', 0),
                    trade.get('price', 0),
                    trade.get('conditionId', ''),
                    datetime.fromtimestamp(trade.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S') if trade.get('timestamp') else '',
                    trade.get('transactionHash', ''),
                    trade.get('eventSlug', '')
                ])

        print(f"✓ Exported {len(trades)} trades to {filename}")
        return filename

    def generate_summary(self, positions, trades):
        """Generate summary statistics"""

        print("\n" + "="*80)
        print("POLYMARKET API DATA SUMMARY")
        print("="*80)

        if positions:
            total_pnl = sum(pos.get('realizedPnl', 0) for pos in positions)
            winning_positions = [p for p in positions if p.get('realizedPnl', 0) > 0]
            losing_positions = [p for p in positions if p.get('realizedPnl', 0) < 0]
            breakeven_positions = [p for p in positions if p.get('realizedPnl', 0) == 0]

            print(f"\nCLOSED POSITIONS (Complete Data - No API Limits):")
            print(f"  Total Positions: {len(positions)}")
            print(f"  Winning Positions: {len(winning_positions)}")
            print(f"  Losing Positions: {len(losing_positions)}")
            print(f"  Breakeven Positions: {len(breakeven_positions)}")
            print(f"  Win Rate: {len(winning_positions)/len(positions)*100:.1f}%")
            print(f"  Total Realized PnL: ${total_pnl:.2f}")

            if winning_positions:
                best_trade = max(winning_positions, key=lambda x: x.get('realizedPnl', 0))
                print(f"\n  Best Trade:")
                print(f"    Market: {best_trade.get('title', 'Unknown')}")
                print(f"    Outcome: {best_trade.get('outcome', 'Unknown')}")
                print(f"    PnL: ${best_trade.get('realizedPnl', 0):.2f}")

            if losing_positions:
                worst_trade = min(losing_positions, key=lambda x: x.get('realizedPnl', 0))
                print(f"\n  Worst Trade:")
                print(f"    Market: {worst_trade.get('title', 'Unknown')}")
                print(f"    Outcome: {worst_trade.get('outcome', 'Unknown')}")
                print(f"    PnL: ${worst_trade.get('realizedPnl', 0):.2f}")

        if trades:
            buys = [t for t in trades if t.get('side') == 'BUY']
            sells = [t for t in trades if t.get('side') == 'SELL']

            print(f"\nTRADES (May be incomplete if >4000 total):")
            print(f"  Total Trades Fetched: {len(trades)}")
            print(f"  Buy Orders: {len(buys)}")
            print(f"  Sell Orders: {len(sells)}")

            if buys:
                total_bought = sum(float(t.get('size', 0)) * float(t.get('price', 0)) for t in buys)
                print(f"  Total Spent on Buys: ${total_bought:.2f}")

            if sells:
                total_sold = sum(float(t.get('size', 0)) * float(t.get('price', 0)) for t in sells)
                print(f"  Total Received from Sells: ${total_sold:.2f}")

        print("\n" + "="*80)
        print("NOTE: For complete analysis, use the closed positions data.")
        print("      The trades data may be limited by API restrictions.")
        print("="*80)


def main():
    from datetime import datetime, timedelta

    # Get wallet address from command line or prompt
    if len(sys.argv) >= 2 and not sys.argv[1].startswith('--'):
        wallet_address = sys.argv[1]
        days_back = None
    else:
        print("\n" + "="*60)
        print("Polymarket Data Fetcher")
        print("="*60)
        wallet_address = input("\nEnter wallet address to analyze: ").strip()

        if not wallet_address:
            print("Error: Wallet address is required")
            sys.exit(1)

        # Ask for timeframe
        days_input = input("\nHow many days back to analyze? (press Enter for all data): ").strip()
        days_back = int(days_input) if days_input else None

    fetcher = PolymarketAPIFetcher()

    # Fetch data
    print(f"\nFetching data for wallet: {wallet_address}...")
    if days_back:
        print(f"Timeframe: Last {days_back} days")
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())
    else:
        print("Timeframe: All available data")
        cutoff_timestamp = None

    # Pass cutoff_timestamp to fetch methods for optimized fetching
    positions = fetcher.get_all_closed_positions(wallet_address, cutoff_timestamp)
    trades = fetcher.get_all_trades(wallet_address, cutoff_timestamp)

    # Export to CSV
    if positions:
        fetcher.export_closed_positions_csv(positions, wallet_address, trades)

    if trades:
        fetcher.export_trades_csv(trades, wallet_address)

    # Generate summary
    fetcher.generate_summary(positions, trades)


if __name__ == '__main__':
    main()

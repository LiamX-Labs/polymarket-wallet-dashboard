#!/usr/bin/env python3
"""
Polymarket Wallet Analysis Tool

Analyzes wallet transactions on Polygon to track deposits, withdrawals,
and net balance for copy trading performance monitoring.
"""

import requests
import time
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal


class PolygonScanAPI:
    """Wrapper for PolygonScan API V2 (Etherscan) to fetch token transactions."""

    BASE_URL = "https://api.etherscan.io/v2/api"
    POLYGON_CHAIN_ID = "137"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            api_key: Etherscan API key (required - works for Polygon via V2 API)
        """
        self.api_key = api_key or "YourApiKeyToken"
        self.session = requests.Session()

    def get_token_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None,
        startblock: int = 0,
        endblock: int = 99999999,
        page: int = 1,
        offset: int = 10000,
        sort: str = "asc"
    ) -> List[Dict]:
        """
        Fetch ERC-20 token transfer events for an address.

        Args:
            address: Wallet address to analyze
            contract_address: Optional token contract address to filter (e.g., USDC)
            startblock: Starting block number
            endblock: Ending block number
            page: Page number for pagination
            offset: Number of transactions per page (max 10000)
            sort: Sort order ('asc' or 'desc')

        Returns:
            List of transaction dictionaries
        """
        params = {
            "chainid": self.POLYGON_CHAIN_ID,
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": startblock,
            "endblock": endblock,
            "page": page,
            "offset": offset,
            "sort": sort,
            "apikey": self.api_key
        }

        if contract_address:
            params["contractaddress"] = contract_address

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data["status"] == "1":
                return data["result"]
            elif data["message"] == "No transactions found":
                return []
            elif "Invalid API Key" in data.get("result", ""):
                print("\n" + "="*80)
                print("ERROR: Invalid PolygonScan API Key")
                print("="*80)
                print("You need to get a FREE API key from PolygonScan:")
                print("1. Visit: https://polygonscan.com/apis")
                print("2. Sign up for a free account")
                print("3. Generate an API key")
                print("4. Run the tool with: --api-key YOUR_API_KEY")
                print("="*80 + "\n")
                raise Exception("Invalid API Key - please get a free key from polygonscan.com/apis")
            elif "Max rate limit reached" in data.get("message", ""):
                print("\nRate limit reached. Waiting 1 second...")
                time.sleep(1)
                return []
            else:
                # Check if this is the placeholder key issue
                if self.api_key == "YourApiKeyToken":
                    print("\n" + "="*80)
                    print("ERROR: Using Placeholder API Key")
                    print("="*80)
                    print("You need to get a FREE API key from PolygonScan:")
                    print("1. Visit: https://polygonscan.com/apis")
                    print("2. Sign up for a free account")
                    print("3. Generate an API key")
                    print("4. Run the tool with: --api-key YOUR_API_KEY")
                    print("\nWithout an API key, the tool cannot fetch transaction data.")
                    print("="*80 + "\n")
                raise Exception(f"API Error: {data.get('message', 'Unknown error')} - Get a free API key from polygonscan.com/apis")

        except requests.exceptions.RequestException as e:
            print(f"Error fetching transactions: {e}")
            return []

    def get_all_token_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch all token transfers for an address (handles pagination).

        Args:
            address: Wallet address to analyze
            contract_address: Optional token contract address to filter

        Returns:
            Complete list of all transactions
        """
        all_transactions = []
        page = 1
        offset = 10000  # Max allowed by API

        print(f"Fetching transactions for {address}...")

        while True:
            print(f"  Fetching page {page}...")
            transactions = self.get_token_transfers(
                address=address,
                contract_address=contract_address,
                page=page,
                offset=offset
            )

            if not transactions:
                break

            all_transactions.extend(transactions)

            # If we got less than offset, we've reached the end
            if len(transactions) < offset:
                break

            page += 1
            time.sleep(0.2)  # Rate limiting courtesy

        print(f"  Total transactions fetched: {len(all_transactions)}")
        return all_transactions


class WalletAnalyzer:
    """Analyzes wallet transactions to calculate deposits, withdrawals, and net balance."""

    # Stablecoin contract addresses on Polygon
    USDC_CONTRACT = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # USDC native on Polygon
    USDC_LEGACY = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # Legacy USDC (bridged)
    PUSD_CONTRACT = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"  # Polymarket USD (pUSD)

    # Polymarket contract addresses - these are TRADING, not deposits/withdrawals
    # Note: pUSD minting/burning from 0x0000... address is ALSO considered trading
    POLYMARKET_CONTRACTS = {
        "0xe111180000d2663c0091e4f400237545b87b996b",  # CTF Exchange
        "0xe2222d279d744050d28e00520010520000310f59",  # Neg Risk CTF Exchange
        "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296",  # Neg Risk Adapter
        "0x4d97dcd97ec945f40cf65f87097ace5ea0476045",  # Conditional Tokens (CTF)
        "0x6bbcef9f7ef3b6c592c99e0f206a0de94ad0925f",  # pUSD (implementation)
        "0x93070a847efef7f70739046a929d47a521f5b8ee",  # CollateralOnramp
        "0x2957922eb93258b93368531d39facca3b4dc5854",  # CollateralOfframp
        "0xebc2459ec962869ca4c0bd1e06368272732bcb08",  # PermissionedRamp
        "0xada100db00ca00073811820692005400218fce1f",  # CtfCollateralAdapter
        "0xada2005600dec949baf300f4c6120000bdb6eaab",  # NegRiskCtfCollateralAdapter
        "0x0000000000000000000000000000000000000000",  # Zero address (pUSD minting/burning)
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the analyzer with PolygonScan API client."""
        self.api = PolygonScanAPI(api_key)

    def analyze_wallet(self, wallet_address: str, token_contract: Optional[str] = None, days_back: Optional[int] = None) -> Dict:
        """
        Analyze a wallet's deposit/withdrawal balance.

        Args:
            wallet_address: The wallet address to analyze
            token_contract: Optional specific token contract (defaults to USDC)
            days_back: Optional number of days to look back (None = all time)

        Returns:
            Dictionary with analysis results
        """
        from datetime import datetime, timedelta

        wallet_address = wallet_address.lower()

        # Default to all stablecoins if no contract specified
        if token_contract is None:
            # Fetch all stablecoin contracts and merge
            print("\nFetching pUSD (Polymarket USD) transactions...")
            txs_pusd = self.api.get_all_token_transfers(wallet_address, self.PUSD_CONTRACT)

            print("\nFetching USDC (native) transactions...")
            txs_native = self.api.get_all_token_transfers(wallet_address, self.USDC_CONTRACT)

            print("\nFetching USDC (legacy bridged) transactions...")
            txs_legacy = self.api.get_all_token_transfers(wallet_address, self.USDC_LEGACY)

            transactions = txs_pusd + txs_native + txs_legacy
        else:
            transactions = self.api.get_all_token_transfers(wallet_address, token_contract)

        # Filter by timeframe if specified
        if days_back and transactions:
            cutoff_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())
            original_count = len(transactions)
            transactions = [tx for tx in transactions if int(tx.get('timeStamp', 0)) >= cutoff_timestamp]
            print(f"\nFiltered transactions: {len(transactions)}/{original_count} within timeframe")

        if not transactions:
            return {
                "wallet": wallet_address,
                "total_transactions": 0,
                "deposits": Decimal("0"),
                "withdrawals": Decimal("0"),
                "net_balance": Decimal("0"),
                "deposit_count": 0,
                "withdrawal_count": 0
            }

        return self._calculate_balance(wallet_address, transactions)

    def _is_polymarket_contract(self, address: str) -> bool:
        """Check if an address is a Polymarket contract."""
        return address.lower() in self.POLYMARKET_CONTRACTS

    def _calculate_balance(self, wallet_address: str, transactions: List[Dict]) -> Dict:
        """
        Calculate deposits, withdrawals, and net balance from transactions.
        Separates actual deposits/withdrawals from Polymarket trading activity.

        Args:
            wallet_address: The wallet being analyzed
            transactions: List of transaction data

        Returns:
            Analysis results dictionary
        """
        # Sort transactions by timestamp to identify the first one
        sorted_txs = sorted(transactions, key=lambda x: int(x.get("timeStamp", 0)))

        # External deposits/withdrawals (actual money in/out)
        total_deposits = Decimal("0")
        total_withdrawals = Decimal("0")
        deposit_count = 0
        withdrawal_count = 0

        # Polymarket trading activity (not real deposits/withdrawals)
        trading_deposits = Decimal("0")
        trading_withdrawals = Decimal("0")
        trading_deposit_count = 0
        trading_withdrawal_count = 0

        # Track unique transactions to avoid duplicates
        seen_txs = set()
        deposit_txs = []
        withdrawal_txs = []
        trading_deposit_txs = []
        trading_withdrawal_txs = []

        # Track if we've seen the initial deposit
        seen_initial_deposit = False

        for tx in sorted_txs:
            tx_hash = tx["hash"]

            # Skip duplicates
            if tx_hash in seen_txs:
                continue
            seen_txs.add(tx_hash)

            # Get transaction details
            from_address = tx["from"].lower()
            to_address = tx["to"].lower()
            value = Decimal(tx["value"])
            decimals = int(tx["tokenDecimal"])
            token_symbol = tx["tokenSymbol"]

            # Convert to human-readable amount
            amount = value / (Decimal(10) ** decimals)

            # Create transaction record
            tx_record = {
                "hash": tx_hash,
                "amount": amount,
                "token": token_symbol,
                "timestamp": datetime.fromtimestamp(int(tx["timeStamp"]))
            }

            # Categorize transaction
            if to_address == wallet_address:
                # Money coming IN
                tx_record["from"] = from_address

                # Special case: First transaction from zero address is the initial deposit
                if (not seen_initial_deposit and
                    from_address == "0x0000000000000000000000000000000000000000"):
                    # This is the initial pUSD minting = your deposit
                    total_deposits += amount
                    deposit_count += 1
                    deposit_txs.append(tx_record)
                    seen_initial_deposit = True
                elif self._is_polymarket_contract(from_address):
                    # Coming FROM Polymarket = Trading activity (e.g., closing position)
                    trading_deposits += amount
                    trading_deposit_count += 1
                    trading_deposit_txs.append(tx_record)
                else:
                    # Coming from external address = Real deposit
                    total_deposits += amount
                    deposit_count += 1
                    deposit_txs.append(tx_record)

            elif from_address == wallet_address:
                # Money going OUT
                tx_record["to"] = to_address

                if self._is_polymarket_contract(to_address):
                    # Going TO Polymarket = Trading activity (e.g., opening position)
                    trading_withdrawals += amount
                    trading_withdrawal_count += 1
                    trading_withdrawal_txs.append(tx_record)
                else:
                    # Going to external address = Real withdrawal
                    total_withdrawals += amount
                    withdrawal_count += 1
                    withdrawal_txs.append(tx_record)

        # Calculate net balances
        net_balance = total_deposits - total_withdrawals
        net_trading = trading_deposits - trading_withdrawals

        return {
            "wallet": wallet_address,
            "total_transactions": len(seen_txs),

            # External deposits/withdrawals (real money movement)
            "deposits": total_deposits,
            "withdrawals": total_withdrawals,
            "net_balance": net_balance,
            "deposit_count": deposit_count,
            "withdrawal_count": withdrawal_count,
            "deposit_transactions": deposit_txs,
            "withdrawal_transactions": withdrawal_txs,

            # Polymarket trading activity
            "trading_deposits": trading_deposits,
            "trading_withdrawals": trading_withdrawals,
            "net_trading": net_trading,
            "trading_deposit_count": trading_deposit_count,
            "trading_withdrawal_count": trading_withdrawal_count,
            "trading_deposit_transactions": trading_deposit_txs,
            "trading_withdrawal_transactions": trading_withdrawal_txs,

            "token_symbol": transactions[0]["tokenSymbol"] if transactions else "N/A"
        }

    def print_analysis(self, analysis: Dict, show_details: bool = False):
        """
        Print a formatted analysis report.

        Args:
            analysis: Analysis results dictionary
            show_details: Whether to show individual transactions
        """
        print("\n" + "="*80)
        print("POLYMARKET WALLET ANALYSIS REPORT")
        print("="*80)
        print(f"\nWallet Address: {analysis['wallet']}")
        print(f"Token: {analysis['token_symbol']}")
        print(f"\nTotal Transactions: {analysis['total_transactions']}")

        # External deposits/withdrawals
        print(f"\n{'-'*80}")
        print("EXTERNAL TRANSFERS (Real Money In/Out)")
        print(f"{'-'*80}")
        print(f"  Deposits (IN):      {analysis['deposit_count']:>6} transactions")
        print(f"  Withdrawals (OUT):  {analysis['withdrawal_count']:>6} transactions")

        # Polymarket trading
        print(f"\n{'-'*80}")
        print("POLYMARKET TRADING ACTIVITY")
        print(f"{'-'*80}")
        print(f"  To Polymarket:      {analysis['trading_withdrawal_count']:>6} transactions")
        print(f"  From Polymarket:    {analysis['trading_deposit_count']:>6} transactions")

        print(f"\n{'='*80}")
        print("EXTERNAL BALANCE SUMMARY (Your Real Money)")
        print("="*80)
        print(f"Total Deposits:     {analysis['deposits']:>20,.6f} {analysis['token_symbol']}")
        print(f"Total Withdrawals:  {analysis['withdrawals']:>20,.6f} {analysis['token_symbol']}")
        print(f"{'-'*80}")

        net = analysis['net_balance']
        if net >= 0:
            print(f"Net Balance:        {net:>20,.6f} {analysis['token_symbol']}")
            print(f"\nInterpretation: You have deposited MORE than withdrawn")
            print(f"                This means you still have funds in the wallet/Polymarket")
        else:
            print(f"Net Balance:        {net:>20,.6f} {analysis['token_symbol']}")
            print(f"\nInterpretation: You have withdrawn MORE than deposited")
            print(f"                This means you've taken out profits (GOOD!)")

        # Trading balance
        print(f"\n{'='*80}")
        print("POLYMARKET TRADING BALANCE")
        print("="*80)
        print(f"Sent to Polymarket:     {analysis['trading_withdrawals']:>20,.6f} {analysis['token_symbol']}")
        print(f"Received from Polymarket: {analysis['trading_deposits']:>20,.6f} {analysis['token_symbol']}")
        print(f"{'-'*80}")

        net_trading = analysis['net_trading']
        if net_trading >= 0:
            print(f"Net Trading:        {net_trading:>20,.6f} {analysis['token_symbol']}")
            print(f"\nInterpretation: Polymarket has returned MORE than you sent")
            print(f"                This indicates PROFITABLE trading!")
        else:
            print(f"Net Trading:        {net_trading:>20,.6f} {analysis['token_symbol']}")
            print(f"\nInterpretation: Polymarket has returned LESS than you sent")
            print(f"                This indicates LOSING trades or open positions")

        # Overall summary
        print(f"\n{'='*80}")
        print("OVERALL SUMMARY")
        print("="*80)
        total_in = analysis['deposits'] + analysis['trading_deposits']
        total_out = analysis['withdrawals'] + analysis['trading_withdrawals']
        print(f"Total IN (all sources):  {total_in:>20,.6f} {analysis['token_symbol']}")
        print(f"Total OUT (all sinks):   {total_out:>20,.6f} {analysis['token_symbol']}")
        print(f"Net Change:              {total_in - total_out:>20,.6f} {analysis['token_symbol']}")
        print("="*80)

        if show_details:
            self._print_transaction_details(analysis)

    def _print_transaction_details(self, analysis: Dict):
        """Print detailed transaction breakdown."""
        print("\n" + "="*80)
        print("EXTERNAL DEPOSIT DETAILS:")
        print("="*80)
        if analysis['deposit_transactions']:
            for tx in analysis['deposit_transactions'][:10]:  # Show first 10
                print(f"{tx['timestamp']:%Y-%m-%d %H:%M:%S} | "
                      f"{tx['amount']:>15,.6f} {tx['token']} | "
                      f"From: {tx['from'][:10]}...")
            if len(analysis['deposit_transactions']) > 10:
                print(f"... and {len(analysis['deposit_transactions']) - 10} more deposits")
        else:
            print("No external deposits found")

        print("\n" + "="*80)
        print("EXTERNAL WITHDRAWAL DETAILS:")
        print("="*80)
        if analysis['withdrawal_transactions']:
            for tx in analysis['withdrawal_transactions'][:10]:  # Show first 10
                print(f"{tx['timestamp']:%Y-%m-%d %H:%M:%S} | "
                      f"{tx['amount']:>15,.6f} {tx['token']} | "
                      f"To: {tx['to'][:10]}...")
            if len(analysis['withdrawal_transactions']) > 10:
                print(f"... and {len(analysis['withdrawal_transactions']) - 10} more withdrawals")
        else:
            print("No external withdrawals found")

        print("\n" + "="*80)
        print("POLYMARKET TRADING - SENT TO POLYMARKET:")
        print("="*80)
        if analysis['trading_withdrawal_transactions']:
            for tx in analysis['trading_withdrawal_transactions'][:10]:
                print(f"{tx['timestamp']:%Y-%m-%d %H:%M:%S} | "
                      f"{tx['amount']:>15,.6f} {tx['token']} | "
                      f"To: {tx['to'][:10]}...")
            if len(analysis['trading_withdrawal_transactions']) > 10:
                print(f"... and {len(analysis['trading_withdrawal_transactions']) - 10} more")
        else:
            print("No trades sent to Polymarket")

        print("\n" + "="*80)
        print("POLYMARKET TRADING - RECEIVED FROM POLYMARKET:")
        print("="*80)
        if analysis['trading_deposit_transactions']:
            for tx in analysis['trading_deposit_transactions'][:10]:
                print(f"{tx['timestamp']:%Y-%m-%d %H:%M:%S} | "
                      f"{tx['amount']:>15,.6f} {tx['token']} | "
                      f"From: {tx['from'][:10]}...")
            if len(analysis['trading_deposit_transactions']) > 10:
                print(f"... and {len(analysis['trading_deposit_transactions']) - 10} more")
        else:
            print("No trades received from Polymarket")


def main():
    """Main entry point for the wallet analyzer CLI."""
    import argparse

    # Default API key
    DEFAULT_API_KEY = "ZA1X87TCSVVD53WECWZZ8UWJ7Y1VPKJ94A"

    parser = argparse.ArgumentParser(
        description="Analyze Polymarket wallet deposits and withdrawals"
    )
    parser.add_argument(
        "wallet",
        nargs='?',
        help="Wallet address to analyze"
    )
    parser.add_argument(
        "--api-key",
        help="PolygonScan API key (uses default if not provided)",
        default=DEFAULT_API_KEY
    )
    parser.add_argument(
        "--token",
        help="Specific token contract address (defaults to USDC)",
        default=None
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed transaction breakdown"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days back to analyze (default: all time)",
        default=None
    )

    args = parser.parse_args()

    # Prompt for wallet address if not provided
    if not args.wallet:
        from datetime import datetime, timedelta

        print("\n" + "="*60)
        print("Polymarket Wallet Analyzer")
        print("="*60)
        args.wallet = input("\nEnter wallet address to analyze: ").strip()

        if not args.wallet:
            print("Error: Wallet address is required")
            sys.exit(1)

        # Ask for timeframe
        days_input = input("\nHow many days back to analyze? (press Enter for all data): ").strip()
        args.days = int(days_input) if days_input else None

        print("="*80 + "\n")

    # Print timeframe info
    if args.days:
        print(f"Timeframe: Last {args.days} days\n")
    else:
        print("Timeframe: All available data\n")

    # Create analyzer
    analyzer = WalletAnalyzer(api_key=args.api_key)

    # Analyze wallet
    try:
        analysis = analyzer.analyze_wallet(args.wallet, args.token, days_back=args.days)
        # Print results
        analyzer.print_analysis(analysis, show_details=args.details)
    except Exception as e:
        print(f"\nAnalysis failed: {e}")
        print("\nIf you haven't already, please get a free API key from:")
        print("https://polygonscan.com/apis")
        exit(1)


if __name__ == "__main__":
    main()

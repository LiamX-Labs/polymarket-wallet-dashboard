"""
Analysis wrapper for Telegram bot
Reuses existing Polymarket analysis scripts
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json

# Add scripts directory to path
scripts_dir = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, scripts_dir)

from polymarket_api_fetcher import PolymarketAPIFetcher


def run_wallet_analysis(wallet_address: str, days_back: int = None) -> dict:
    """
    Run complete wallet analysis using existing Polymarket API fetcher

    Args:
        wallet_address: Ethereum wallet address
        days_back: Number of days to look back (None for all data)

    Returns:
        Dictionary containing all analysis results
    """

    # Calculate cutoff timestamp
    cutoff_timestamp = None
    if days_back:
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())

    # Fetch data using existing fetcher
    fetcher = PolymarketAPIFetcher()

    print(f"Fetching data for {wallet_address[:10]}...")
    positions = fetcher.get_all_performance_positions(wallet_address, cutoff_timestamp)
    trades = fetcher.get_all_trades(wallet_address, cutoff_timestamp)

    if not positions:
        raise ValueError("No performance positions found for this wallet in the specified timeframe")

    # Convert positions to DataFrame
    df = pd.DataFrame(positions)

    # Ensure required columns
    df['Timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df['Realized PnL'] = df['realizedPnl'].astype(float)
    df['Avg Price'] = df['avgPrice'].astype(float)
    df['Total Bought'] = df['totalBought'].astype(float)  # Number of shares
    df['Market Title'] = df['title']
    df['Outcome'] = df['outcome']

    # Calculate position size in dollars (investment amount)
    df['Position Size ($)'] = df['Total Bought'] * df['Avg Price']

    # Calculate comprehensive metrics
    metrics = calculate_metrics(df, trades)

    # Get top trades
    top_trades = get_top_trades(df)

    return {
        'wallet': wallet_address,
        'positions': positions,
        'trades': trades,
        'metrics': metrics,
        'df': df,
        'top_winners': top_trades['winners'],
        'top_losers': top_trades['losers']
    }


def calculate_metrics(df: pd.DataFrame, trades: list) -> dict:
    """
    Calculate performance metrics (from generate_performance_report.py logic)

    Args:
        df: DataFrame with position data
        trades: List of trade dicts

    Returns:
        Dictionary of calculated metrics
    """

    # Basic metrics
    total_pnl = df['Realized PnL'].sum()
    num_positions = len(df)
    winning = df[df['Realized PnL'] > 0]
    losing = df[df['Realized PnL'] < 0]

    win_rate = len(winning) / num_positions * 100 if num_positions > 0 else 0
    avg_win = winning['Realized PnL'].mean() if len(winning) > 0 else 0
    avg_loss = losing['Realized PnL'].mean() if len(losing) > 0 else 0
    best_trade = df['Realized PnL'].max()
    worst_trade = df['Realized PnL'].min()

    # Risk metrics
    risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    total_wins = winning['Realized PnL'].sum()
    total_losses = abs(losing['Realized PnL'].sum())
    profit_factor = total_wins / total_losses if total_losses > 0 else 0

    # Drawdown calculation
    df_sorted = df.sort_values('Timestamp')
    df_sorted['Cumulative PnL'] = df_sorted['Realized PnL'].cumsum()
    running_max = df_sorted['Cumulative PnL'].expanding().max()
    drawdown = df_sorted['Cumulative PnL'] - running_max
    max_drawdown = drawdown.min()

    # Consecutive wins/losses
    df_sorted['Win'] = df_sorted['Realized PnL'] > 0
    streaks = calculate_streaks(df_sorted['Win'].tolist())
    max_consecutive_wins = streaks['max_wins']
    max_consecutive_losses = streaks['max_losses']

    # HFT Detection Metrics
    df_sorted['Hour'] = df_sorted['Timestamp'].dt.floor('h')
    positions_per_hour = df_sorted.groupby('Hour').size()
    avg_positions_per_hour = positions_per_hour.mean()
    median_positions_per_hour = positions_per_hour.median()
    max_positions_per_hour = positions_per_hour.max()

    # Time between positions
    time_diffs = df_sorted['Timestamp'].diff()
    median_time_between = time_diffs.median().total_seconds() / 60 if len(time_diffs) > 1 else 0

    # Trading duration
    trading_duration_hours = (df_sorted['Timestamp'].max() - df_sorted['Timestamp'].min()).total_seconds() / 3600

    # Trading style classification
    if median_time_between < 5 and avg_positions_per_hour > 10:
        trading_style = "⚡ HFT Bot"
    elif avg_positions_per_hour > 5:
        trading_style = "📈 Active Trader"
    else:
        trading_style = "📊 Normal Trader"

    # Position sizing - calculate from dollar investment amounts
    avg_position_size = df['Position Size ($)'].mean()
    median_position_size = df['Position Size ($)'].median()

    return {
        'trading_style': trading_style,
        'total_pnl': total_pnl,
        'num_positions': num_positions,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'best_trade': best_trade,
        'worst_trade': worst_trade,
        'risk_reward': risk_reward,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'max_consecutive_wins': max_consecutive_wins,
        'max_consecutive_losses': max_consecutive_losses,
        'avg_positions_per_hour': avg_positions_per_hour,
        'median_positions_per_hour': median_positions_per_hour,
        'max_positions_per_hour': max_positions_per_hour,
        'median_time_between': median_time_between,
        'trading_duration_hours': trading_duration_hours,
        'avg_position_size': avg_position_size,
        'median_position_size': median_position_size,
        'total_trades': len(trades) if trades else 0
    }


def calculate_streaks(wins: list) -> dict:
    """
    Calculate consecutive win/loss streaks

    Args:
        wins: List of booleans (True for win, False for loss)

    Returns:
        Dict with max_wins and max_losses
    """

    win_streaks = []
    loss_streaks = []
    current_streak = 0
    last_was_win = None

    for is_win in wins:
        if is_win:
            if last_was_win == True:
                current_streak += 1
            else:
                if last_was_win == False and current_streak > 0:
                    loss_streaks.append(current_streak)
                current_streak = 1
            last_was_win = True
        else:
            if last_was_win == False:
                current_streak += 1
            else:
                if last_was_win == True and current_streak > 0:
                    win_streaks.append(current_streak)
                current_streak = 1
            last_was_win = False

    # Add final streak
    if current_streak > 0:
        if last_was_win:
            win_streaks.append(current_streak)
        else:
            loss_streaks.append(current_streak)

    return {
        'max_wins': max(win_streaks) if win_streaks else 0,
        'max_losses': max(loss_streaks) if loss_streaks else 0
    }


def get_top_trades(df: pd.DataFrame, n: int = 5) -> dict:
    """
    Get top winning and losing trades

    Args:
        df: DataFrame with position data
        n: Number of top trades to return

    Returns:
        Dict with 'winners' and 'losers' lists
    """

    winners = df.nlargest(n, 'Realized PnL')
    losers = df.nsmallest(n, 'Realized PnL')

    def format_trade(row):
        return {
            'market': row['Market Title'],
            'outcome': row['Outcome'],
            'pnl': row['Realized PnL'],
            'avg_price': row['Avg Price'],
            'size': row['Total Bought']
        }

    return {
        'winners': [format_trade(row) for _, row in winners.iterrows()],
        'losers': [format_trade(row) for _, row in losers.iterrows()]
    }


# Cache for rate limiting (simple in-memory cache)
_analysis_cache = {}
_cache_timestamps = {}

def get_cached_analysis(wallet: str, max_age_seconds: int = 3600):
    """
    Get cached analysis if available and not expired

    Args:
        wallet: Wallet address
        max_age_seconds: Maximum cache age in seconds

    Returns:
        Cached results or None
    """
    if wallet not in _analysis_cache:
        return None

    cache_time = _cache_timestamps.get(wallet, 0)
    if (datetime.now().timestamp() - cache_time) > max_age_seconds:
        # Cache expired
        del _analysis_cache[wallet]
        del _cache_timestamps[wallet]
        return None

    return _analysis_cache[wallet]


def cache_analysis(wallet: str, results: dict):
    """
    Cache analysis results

    Args:
        wallet: Wallet address
        results: Analysis results to cache
    """
    _analysis_cache[wallet] = results
    _cache_timestamps[wallet] = datetime.now().timestamp()


def export_closed_trades_csv(analysis_results: dict) -> str:
    """
    Export closed trades to CSV file matching Polymarket format

    Args:
        analysis_results: Dictionary containing analysis results from run_wallet_analysis

    Returns:
        Path to generated CSV file
    """
    import csv

    positions = analysis_results['positions']
    trades = analysis_results.get('trades', [])
    wallet = analysis_results['wallet']

    if not positions:
        raise ValueError("No positions to export")

    # Count trades per (condition ID + outcome) if trades data is available
    trade_counts = {}
    if trades:
        for trade in trades:
            condition_id = trade.get('conditionId', '')
            outcome = trade.get('outcome', '')
            position_key = f"{condition_id}:{outcome}"
            trade_counts[position_key] = trade_counts.get(position_key, 0) + 1

    # Save to reports directory (same as HTML reports)
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    csv_filename = os.path.join(
        reports_dir,
        f'polymarket_closed_trades_{wallet[:10]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header matching Polymarket format
        writer.writerow([
            'Market Title',
            'Outcome',
            'Condition ID',
            'Realized PnL',
            'Avg Price',
            'Total Bought',
            'Position Size ($)',
            'Current Price',
            'Trades',
            'Timestamp',
            'Date',
            'Event Slug',
            'End Date'
        ])

        # Data rows
        for pos in positions:
            condition_id = pos.get('conditionId', '')
            outcome = pos.get('outcome', '')
            position_key = f"{condition_id}:{outcome}"
            num_trades = trade_counts.get(position_key, 0) if trades else 'N/A'

            # Calculate position size in dollars
            avg_price = float(pos.get('avgPrice', 0) or 0)
            total_bought = float(pos.get('totalBought', 0) or 0)
            position_size = avg_price * total_bought

            timestamp = pos.get('timestamp', 0)
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else ''
            date_only = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d') if timestamp else ''

            writer.writerow([
                pos.get('title', ''),
                pos.get('outcome', ''),
                condition_id,
                pos.get('realizedPnl', 0),
                avg_price,
                total_bought,
                f"{position_size:.2f}",
                pos.get('curPrice', 0),
                num_trades,
                date_str,
                date_only,
                pos.get('eventSlug', ''),
                pos.get('endDate', '')
            ])

    print(f"✓ Exported {len(positions)} closed trades to {csv_filename}")
    return csv_filename


def generate_html_report(analysis_results: dict) -> str:
    """
    Generate interactive HTML report from analysis results

    Args:
        analysis_results: Dictionary containing analysis results from run_wallet_analysis

    Returns:
        Path to generated HTML file
    """
    df = analysis_results['df']
    metrics = analysis_results['metrics']
    wallet = analysis_results['wallet']

    # Calculate sorted dataframe for cumulative PnL
    df_sorted = df.sort_values('Timestamp')
    df_sorted['Cumulative PnL'] = df_sorted['Realized PnL'].cumsum()

    # Calculate drawdown
    running_max = df_sorted['Cumulative PnL'].expanding().max()
    drawdown = (df_sorted['Cumulative PnL'] - running_max).tolist()

    # Prepare chart data
    chart_data = {
        'cumulative_pnl': {
            'timestamps': df_sorted['Timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
            'values': df_sorted['Cumulative PnL'].tolist()
        },
        'win_loss': {
            'labels': ['Wins', 'Losses', 'Breakeven'],
            'values': [
                len(df[df['Realized PnL'] > 0]),
                len(df[df['Realized PnL'] < 0]),
                len(df[df['Realized PnL'] == 0])
            ]
        },
        'pnl_distribution': df['Realized PnL'].tolist(),
        'outcome_pnl': {
            'outcomes': df.groupby('Outcome')['Realized PnL'].sum().index.tolist(),
            'values': df.groupby('Outcome')['Realized PnL'].sum().tolist()
        },
        'hourly_pnl': {
            'hours': list(range(24)),
            'values': [df_sorted[df_sorted['Timestamp'].dt.hour == h]['Realized PnL'].sum()
                       for h in range(24)]
        },
        'position_sizes': df['Position Size ($)'].tolist(),
        'roi_distribution': (df['Realized PnL'] / df['Position Size ($)'] * 100).tolist(),
        'drawdown': drawdown,
        'entry_vs_pnl': {
            'entry_prices': df['Avg Price'].tolist(),
            'pnl': df['Realized PnL'].tolist()
        },
        'size_vs_pnl': {
            'sizes': df['Position Size ($)'].tolist(),
            'pnl': df['Realized PnL'].tolist()
        }
    }

    # Determine trading style badge class
    trading_style = metrics['trading_style']
    if '⚡' in trading_style:
        badge_class = 'hft'
    elif '📈' in trading_style:
        badge_class = 'active'
    else:
        badge_class = 'normal'

    # Generate metrics cards HTML
    total_pnl = metrics['total_pnl']
    metrics_cards_html = f"""
<div class="metric-card {('positive' if total_pnl > 0 else 'negative')}">
    <div class="metric-label">Total Realized PnL</div>
    <div class="metric-value {('positive' if total_pnl > 0 else 'negative')}">${total_pnl:,.2f}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Trading Style</div>
    <div class="metric-value"><span class="badge {badge_class}">{trading_style}</span></div>
</div>
<div class="metric-card">
    <div class="metric-label">Total Positions</div>
    <div class="metric-value">{metrics['num_positions']:,}</div>
</div>
<div class="metric-card positive">
    <div class="metric-label">Win Rate</div>
    <div class="metric-value">{metrics['win_rate']:.2f}%</div>
</div>
<div class="metric-card positive">
    <div class="metric-label">Average Win</div>
    <div class="metric-value">${metrics['avg_win']:.2f}</div>
</div>
<div class="metric-card negative">
    <div class="metric-label">Average Loss</div>
    <div class="metric-value">${metrics['avg_loss']:.2f}</div>
</div>
<div class="metric-card positive">
    <div class="metric-label">Best Trade</div>
    <div class="metric-value positive">${metrics['best_trade']:.2f}</div>
</div>
<div class="metric-card negative">
    <div class="metric-label">Worst Trade</div>
    <div class="metric-value negative">${metrics['worst_trade']:.2f}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Risk/Reward Ratio</div>
    <div class="metric-value">{metrics['risk_reward']:.2f}</div>
</div>
<div class="metric-card {('positive' if metrics['profit_factor'] > 1 else 'negative')}">
    <div class="metric-label">Profit Factor</div>
    <div class="metric-value">{metrics['profit_factor']:.2f}</div>
</div>
<div class="metric-card negative">
    <div class="metric-label">Max Drawdown</div>
    <div class="metric-value negative">${metrics['max_drawdown']:.2f}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Max Consecutive Wins</div>
    <div class="metric-value">{int(metrics['max_consecutive_wins'])}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Max Consecutive Losses</div>
    <div class="metric-value">{int(metrics['max_consecutive_losses'])}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Avg Position Size</div>
    <div class="metric-value">{metrics['avg_position_size']:.2f}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Avg Positions/Hour</div>
    <div class="metric-value">{metrics['avg_positions_per_hour']:.1f}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Median Time Between Positions</div>
    <div class="metric-value">{metrics['median_time_between']:.1f} min</div>
</div>
<div class="metric-card">
    <div class="metric-label">Total Trades Executed</div>
    <div class="metric-value">{metrics['total_trades']}</div>
</div>
<div class="metric-card">
    <div class="metric-label">Trading Duration</div>
    <div class="metric-value">{metrics['trading_duration_hours']:.1f} hrs</div>
</div>
"""

    # Top winners table
    top_winners_html = ""
    for trade in analysis_results['top_winners']:
        top_winners_html += f"""
    <tr>
        <td>{trade['market'][:80]}</td>
        <td>{trade['outcome']}</td>
        <td class="positive-value">${trade['pnl']:.2f}</td>
        <td>${trade['avg_price']:.4f}</td>
        <td>{trade['size']:.2f}</td>
        <td>N/A</td>
        <td>-</td>
    </tr>
    """

    # Top losers table
    top_losers_html = ""
    for trade in analysis_results['top_losers']:
        top_losers_html += f"""
    <tr>
        <td>{trade['market'][:80]}</td>
        <td>{trade['outcome']}</td>
        <td class="negative-value">${trade['pnl']:.2f}</td>
        <td>${trade['avg_price']:.4f}</td>
        <td>{trade['size']:.2f}</td>
        <td>N/A</td>
        <td>-</td>
    </tr>
    """

    # All positions data for JavaScript
    all_positions_data = []
    for _, row in df.iterrows():
        roi = (row['Realized PnL'] / row['Position Size ($)'] * 100) if row['Position Size ($)'] != 0 else 0
        all_positions_data.append({
            'timestamp': row['Timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'market': row['Market Title'][:60],
            'outcome': row['Outcome'],
            'entry_price': float(row['Avg Price']),
            'size': float(row['Position Size ($)']),  # Dollar amount invested
            'exit_price': 0.0,  # Not available in current data
            'trades': 0,  # Not available
            'pnl': float(row['Realized PnL']),
            'roi': float(roi)
        })

    # Load HTML template
    template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'report_template.html')
    with open(template_path, 'r') as f:
        template = f.read()

    # Replace placeholders
    html_output = template.replace('{{wallet}}', wallet[:10] + '...' + wallet[-6:])
    html_output = html_output.replace('{{timestamp}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    html_output = html_output.replace('{{metrics_cards}}', metrics_cards_html)
    html_output = html_output.replace('{{chart_data}}', json.dumps(chart_data))
    html_output = html_output.replace('{{top_winners}}', top_winners_html)
    html_output = html_output.replace('{{top_losers}}', top_losers_html)
    html_output = html_output.replace('{{all_positions}}', '')  # Will be loaded via JS
    html_output = html_output.replace('{{all_positions_data}}', json.dumps(all_positions_data))
    html_output = html_output.replace('{{total_positions}}', str(len(df)))

    # Save to reports directory
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    html_filename = os.path.join(
        reports_dir,
        f'polymarket_performance_report_{wallet[:10]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
    )

    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html_output)

    return html_filename

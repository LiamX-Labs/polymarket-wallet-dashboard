"""
Text and table formatting utilities for Telegram messages
"""


def format_summary(results: dict) -> str:
    """
    Format analysis summary for Telegram

    Args:
        results: Analysis results dictionary

    Returns:
        HTML-formatted summary message
    """
    metrics = results['metrics']
    wallet = results['wallet']

    # Shorten wallet address for display
    wallet_display = f"{wallet[:10]}...{wallet[-6:]}"

    summary = f"""
<b>📊 Polymarket Analysis Report</b>

<b>Wallet:</b> <code>{wallet_display}</code>
<b>Trading Style:</b> {metrics['trading_style']}

<b>💰 Performance</b>
• Total PnL: <b>${metrics['total_pnl']:.2f}</b>
• Positions: {metrics['num_positions']}
• Win Rate: {metrics['win_rate']:.1f}%
• Profit Factor: {metrics['profit_factor']:.2f}
• Risk/Reward: {metrics['risk_reward']:.2f}

<b>⚡ Trading Activity</b>
• Positions/Hour: {metrics['avg_positions_per_hour']:.1f}
• Time Between Positions: {metrics['median_time_between']:.1f} min
• Total Trades: {metrics['total_trades']}
"""

    return summary.strip()


def format_detailed_metrics(metrics: dict) -> str:
    """
    Format detailed metrics table

    Args:
        metrics: Metrics dictionary

    Returns:
        Pre-formatted ASCII table
    """

    table = f"""
<pre>
┌──────────────────────────┬─────────────┐
│ Metric                   │ Value       │
├──────────────────────────┼─────────────┤
│ Total PnL                │ ${metrics['total_pnl']:>10.2f} │
│ Positions                │ {metrics['num_positions']:>11} │
│ Win Rate                 │ {metrics['win_rate']:>9.1f}% │
│ Avg Win                  │ ${metrics['avg_win']:>10.2f} │
│ Avg Loss                 │ ${metrics['avg_loss']:>10.2f} │
│ Best Trade               │ ${metrics.get('best_trade', 0):>10.2f} │
│ Worst Trade              │ ${metrics.get('worst_trade', 0):>10.2f} │
│ Risk/Reward              │ {metrics['risk_reward']:>11.2f} │
│ Profit Factor            │ {metrics['profit_factor']:>11.2f} │
│ Max Drawdown             │ ${metrics.get('max_drawdown', 0):>10.2f} │
│ Consecutive Wins         │ {metrics.get('max_consecutive_wins', 0):>11} │
│ Consecutive Losses       │ {metrics.get('max_consecutive_losses', 0):>11} │
└──────────────────────────┴─────────────┘
</pre>
"""

    return table.strip()


def format_hft_analysis(metrics: dict) -> str:
    """
    Format HFT detection analysis

    Args:
        metrics: Metrics dictionary

    Returns:
        HTML-formatted HFT analysis
    """

    style = metrics['trading_style']
    positions_per_hour = metrics['avg_positions_per_hour']
    time_between = metrics['median_time_between']
    max_per_hour = metrics.get('max_positions_per_hour', 0)

    message = f"""
<b>🤖 Trading Pattern Analysis</b>

<b>Classification:</b> {style}

<b>Frequency Metrics:</b>
• Avg Positions/Hour: {positions_per_hour:.1f}
• Median Time Between: {time_between:.1f} min
• Peak Activity: {max_per_hour} positions/hour
• Trading Duration: {metrics.get('trading_duration_hours', 0):.1f} hrs

<b>Interpretation:</b>
"""

    if "HFT Bot" in style:
        message += """
This wallet shows characteristics of <b>high-frequency trading</b>:
• Very rapid position taking (&lt;5 min between trades)
• High volume (&gt;10 positions/hour)
• Likely algorithmic/automated trading
"""
    elif "Active Trader" in style:
        message += """
This wallet shows <b>active trading</b> patterns:
• Moderate frequency (5-10 positions/hour)
• Could be manual or semi-automated
• Engaged trader with regular activity
"""
    else:
        message += """
This wallet shows <b>normal trading</b> patterns:
• Low frequency (&lt;5 positions/hour)
• Likely manual/strategic trading
• Casual or long-term positioning
"""

    return message.strip()


def format_top_trades(top_winners: list, top_losers: list) -> str:
    """
    Format top winning and losing trades

    Args:
        top_winners: List of top winning trade dicts
        top_losers: List of top losing trade dicts

    Returns:
        HTML-formatted message
    """

    message = "<b>🏆 Top 5 Best Trades</b>\n\n"

    for i, trade in enumerate(top_winners[:5], 1):
        market = trade['market'][:40] + "..." if len(trade['market']) > 40 else trade['market']
        message += f"{i}. <b>${trade['pnl']:.2f}</b> - {market}\n"
        message += f"   {trade['outcome']} @ ${trade['avg_price']:.4f}\n\n"

    message += "\n<b>📉 Top 5 Worst Trades</b>\n\n"

    for i, trade in enumerate(top_losers[:5], 1):
        market = trade['market'][:40] + "..." if len(trade['market']) > 40 else trade['market']
        message += f"{i}. <b>${trade['pnl']:.2f}</b> - {market}\n"
        message += f"   {trade['outcome']} @ ${trade['avg_price']:.4f}\n\n"

    return message.strip()


def format_error_message(error: Exception) -> str:
    """
    Format error message for user

    Args:
        error: Exception object

    Returns:
        User-friendly error message
    """

    error_str = str(error)

    if "No closed positions found" in error_str:
        return """
❌ <b>No Data Found</b>

This wallet has no closed positions in the specified timeframe.

<b>Possible reasons:</b>
• Wallet has never traded on Polymarket
• No positions closed in the selected timeframe
• Wallet address is incorrect

Try analyzing a different wallet or timeframe.
"""

    elif "max historical activity offset" in error_str or "3000 exceeded" in error_str:
        return """
⚠️ <b>API Limit Reached</b>

This wallet has extensive trading history that exceeds API limits.

<b>Recommendation:</b>
• Analyze a shorter timeframe (7, 14, or 30 days)
• The closed positions data is complete
• Only individual trade details may be limited

The analysis will still show accurate performance metrics.
"""

    elif "Invalid" in error_str or "400" in error_str:
        return f"""
❌ <b>API Error</b>

{error_str}

Please check your wallet address and try again.
"""

    else:
        return f"""
❌ <b>Error</b>

An unexpected error occurred:
<code>{error_str}</code>

Please try again or contact support if the issue persists.
"""


def truncate_text(text: str, max_length: int = 4000) -> str:
    """
    Truncate text to fit Telegram message limits

    Args:
        text: Text to truncate
        max_length: Maximum length (default 4000, leaving room for formatting)

    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text

    return text[:max_length-10] + "\n\n[...]"


def format_tracker_market_alert(alert: dict) -> str:
    """Format per-market Top 5 tracker alert."""
    market = alert["market"]
    top_wallets = alert["top_wallets"]

    lines = [
        "<b>🚨 BTC Market Smart Money Alert</b>",
        "",
        f"<b>Market:</b> {market['title']}",
        f"<b>Timeframe:</b> {market['timeframe']}",
        f"<b>Progress:</b> {market['progress_pct']:.1f}%",
        "",
        f"<b>Top {len(top_wallets)} Wallets (by 7d ROI)</b>",
    ]

    for idx, wallet in enumerate(top_wallets, start=1):
        lines.extend([
            f"{idx}. <code>{wallet['wallet']}</code>",
            f"   Side: <b>{wallet['side']}</b> @ {wallet['entry_price']:.4f}",
            f"   7d ROI: <b>{wallet['roi_7d']:.2f}%</b> | Win Rate: <b>{wallet['win_rate_7d']:.1f}%</b>",
            f"   Copyability: <b>{wallet['copyability_score']:.1f}</b>",
        ])

    return "\n".join(lines)


def format_tracker_daily_report(report: dict) -> str:
    """Format daily Top 10 smart-money report."""
    lines = [
        "<b>📬 Daily Alpha Report (UTC)</b>",
        "",
        f"<b>Date:</b> {report['date_utc']}",
        f"<b>Markets Scanned:</b> {report['markets_scanned']}",
        "",
        "<b>Top 10 Wallets</b>",
    ]

    for idx, wallet in enumerate(report["top_wallets"], start=1):
        lines.append(
            f"{idx}. <code>{wallet['wallet']}</code> | ROI30d: {wallet['roi_30d']:.2f}% | "
            f"Win30d: {wallet['win_rate_30d']:.1f}% | Spec: {wallet['specialization']}"
        )

    return "\n".join(lines)

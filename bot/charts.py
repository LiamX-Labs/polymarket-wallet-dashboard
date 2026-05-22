"""
Chart generation for Telegram bot
Generates matplotlib charts as BytesIO buffers
"""

import io
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from .config import CHART_DPI, CHART_FORMAT

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


def generate_all_charts(df: pd.DataFrame) -> dict:
    """
    Generate all analysis charts

    Args:
        df: DataFrame with position data

    Returns:
        Dict of {chart_name: BytesIO buffer}
    """

    charts = {}

    try:
        charts['Cumulative PnL'] = generate_cumulative_pnl(df)
    except Exception as e:
        print(f"Error generating cumulative PnL chart: {e}")

    try:
        charts['Win/Loss Distribution'] = generate_winloss_pie(df)
    except Exception as e:
        print(f"Error generating win/loss pie: {e}")

    try:
        charts['PnL Distribution'] = generate_pnl_histogram(df)
    except Exception as e:
        print(f"Error generating PnL histogram: {e}")

    try:
        charts['Hourly PnL'] = generate_hourly_pnl(df)
    except Exception as e:
        print(f"Error generating hourly PnL: {e}")

    return charts


def generate_cumulative_pnl(df: pd.DataFrame) -> io.BytesIO:
    """
    Generate cumulative PnL line chart

    Args:
        df: DataFrame with 'Timestamp' and 'Realized PnL' columns

    Returns:
        BytesIO buffer with PNG image
    """

    df_sorted = df.sort_values('Timestamp')
    df_sorted['Cumulative PnL'] = df_sorted['Realized PnL'].cumsum()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df_sorted['Timestamp'], df_sorted['Cumulative PnL'],
            linewidth=2.5, color='#2E86AB')
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.5, linewidth=1.5)

    ax.set_title('Cumulative PnL Over Time', fontweight='bold', fontsize=14)
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Cumulative PnL ($)', fontsize=11)
    ax.grid(True, alpha=0.3)

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    plt.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    fig.savefig(buf, format=CHART_FORMAT, dpi=CHART_DPI, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


def generate_winloss_pie(df: pd.DataFrame) -> io.BytesIO:
    """
    Generate win/loss distribution pie chart

    Args:
        df: DataFrame with 'Realized PnL' column

    Returns:
        BytesIO buffer with PNG image
    """

    winning = len(df[df['Realized PnL'] > 0])
    losing = len(df[df['Realized PnL'] < 0])
    breakeven = len(df[df['Realized PnL'] == 0])

    fig, ax = plt.subplots(figsize=(8, 8))

    sizes = [winning, losing, breakeven]
    labels = [f'Wins ({winning})', f'Losses ({losing})', f'Breakeven ({breakeven})']
    colors = ['#06A77D', '#D72638', '#FFA69E']
    explode = (0.05, 0.05, 0) if breakeven > 0 else (0.05, 0.05)

    # Remove breakeven if zero
    if breakeven == 0:
        sizes = sizes[:2]
        labels = labels[:2]
        colors = colors[:2]
        explode = explode[:2]

    ax.pie(sizes,
           labels=labels,
           autopct='%1.1f%%',
           colors=colors,
           startangle=90,
           explode=explode,
           shadow=True,
           textprops={'fontsize': 11, 'weight': 'bold'})

    ax.set_title('Win/Loss Distribution', fontweight='bold', fontsize=14)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format=CHART_FORMAT, dpi=CHART_DPI, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


def generate_pnl_histogram(df: pd.DataFrame) -> io.BytesIO:
    """
    Generate PnL distribution histogram

    Args:
        df: DataFrame with 'Realized PnL' column

    Returns:
        BytesIO buffer with PNG image
    """

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(df['Realized PnL'], bins=30, color='#4ECDC4',
            edgecolor='black', alpha=0.7, linewidth=1.2)
    ax.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Break-even')

    # Add mean line
    mean_pnl = df['Realized PnL'].mean()
    ax.axvline(x=mean_pnl, color='orange', linestyle='--', linewidth=2,
               label=f'Mean: ${mean_pnl:.2f}')

    ax.set_title('PnL Distribution', fontweight='bold', fontsize=14)
    ax.set_xlabel('Realized PnL ($)', fontsize=11)
    ax.set_ylabel('Frequency', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    # Format x-axis as currency
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format=CHART_FORMAT, dpi=CHART_DPI, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


def generate_hourly_pnl(df: pd.DataFrame) -> io.BytesIO:
    """
    Generate hourly PnL bar chart

    Args:
        df: DataFrame with 'Timestamp' and 'Realized PnL' columns

    Returns:
        BytesIO buffer with PNG image
    """

    df_sorted = df.sort_values('Timestamp')
    df_sorted['Hour'] = df_sorted['Timestamp'].dt.hour
    hourly_pnl = df_sorted.groupby('Hour')['Realized PnL'].sum()

    fig, ax = plt.subplots(figsize=(10, 6))

    # Color bars based on positive/negative
    colors = ['#06A77D' if val >= 0 else '#D72638' for val in hourly_pnl.values]

    ax.bar(hourly_pnl.index, hourly_pnl.values,
           color=colors, edgecolor='black', linewidth=1.2, alpha=0.8)
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)

    ax.set_title('PnL by Hour of Day (UTC)', fontweight='bold', fontsize=14)
    ax.set_xlabel('Hour (UTC)', fontsize=11)
    ax.set_ylabel('Total PnL ($)', fontsize=11)
    ax.set_xticks(range(24))
    ax.grid(True, alpha=0.3, axis='y')

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format=CHART_FORMAT, dpi=CHART_DPI, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


def generate_position_frequency(df: pd.DataFrame) -> io.BytesIO:
    """
    Generate position frequency over time chart

    Args:
        df: DataFrame with 'Timestamp' column

    Returns:
        BytesIO buffer with PNG image
    """

    df_sorted = df.sort_values('Timestamp')
    df_sorted['Hour'] = df_sorted['Timestamp'].dt.floor('h')
    positions_per_hour = df_sorted.groupby('Hour').size()

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(positions_per_hour.index, positions_per_hour.values,
            linewidth=2, color='#9B59B6', marker='o', markersize=3)
    ax.fill_between(positions_per_hour.index, positions_per_hour.values,
                     alpha=0.3, color='#9B59B6')

    # Add average line
    avg_positions = positions_per_hour.mean()
    ax.axhline(y=avg_positions, color='red', linestyle='--', linewidth=1.5,
               label=f'Average: {avg_positions:.1f}/hr')

    ax.set_title('Trading Frequency Over Time', fontweight='bold', fontsize=14)
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Positions per Hour', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format=CHART_FORMAT, dpi=CHART_DPI, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf

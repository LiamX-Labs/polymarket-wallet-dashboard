import sqlite3
import os

db_path = 'data/tracker.sqlite3'

def check_db():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("--- Database Status ---")
    
    tables = ['markets', 'scan_events', 'market_positions', 'wallet_dashboard_summary', 'top_wallet_picks']
    for table in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"Table {table:25}: {count} rows")
        except Exception as e:
            print(f"Table {table:25}: Error - {e}")

    print("\n--- Recent Scan Events ---")
    try:
        rows = conn.execute("SELECT * FROM scan_events ORDER BY id DESC LIMIT 5").fetchall()
        for row in rows:
            print(f"ID: {row['id']}, Market: {row['market_id']}, Time: {row['trigger_ts']}, Status: {row['status']}")
    except Exception as e:
        print(f"Error fetching scan events: {e}")

    print("\n--- Dashboard Summary Samples ---")
    try:
        rows = conn.execute("SELECT wallet, win_rate, total_trades, profit_24h FROM wallet_dashboard_summary LIMIT 5").fetchall()
        for row in rows:
            print(f"Wallet: {row['wallet'][:10]}..., Win Rate: {row['win_rate']:.1f}%, Trades: {row['total_trades']}, Profit 24h: ${row['profit_24h']:.2f}")
    except Exception as e:
        print(f"Error fetching dashboard summary: {e}")

    conn.close()

if __name__ == "__main__":
    check_db()

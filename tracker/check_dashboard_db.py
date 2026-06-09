import sqlite3
import os

db_path = 'data/dashboard.db'

def check_db():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print(f"--- Dashboard DB Status ({db_path}) ---")
    
    tables = ['wallet_dashboard_stats']
    for table in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"Table {table:25}: {count} rows")
        except Exception as e:
            print(f"Table {table:25}: Error - {e}")

    print("\n--- Dashboard Stats Samples ---")
    try:
        rows = conn.execute("SELECT wallet, win_rate, total_trades, profit_24h FROM wallet_dashboard_stats LIMIT 5").fetchall()
        for row in rows:
            print(f"Wallet: {row['wallet'][:10]}..., Win Rate: {row['win_rate']:.1f}%, Trades: {row['total_trades']}, Profit 24h: ${row['profit_24h']:.2f}")
    except Exception as e:
        print(f"Error fetching dashboard stats: {e}")

    conn.close()

if __name__ == "__main__":
    check_db()

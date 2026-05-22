# Database Architecture

## Overview

The Polymarket Wallet Dashboard uses **TWO COMPLETELY SEPARATE DATABASES**:

```
┌─────────────────────────────────────────────────────────────┐
│                    TRACKER DATABASE                          │
│         (Created by market_tracker.py)                       │
│                                                              │
│  Location: /home/william/STRATEGIES/Polymarkets/data/       │
│  File:     tracker.db                                        │
│  Access:   READ-ONLY (never modified by dashboard)          │
│                                                              │
│  Tables:                                                     │
│  • markets                                                   │
│  • scan_events                                               │
│  • market_positions                                          │
│  • wallet_stats_7d                                           │
│  • top_wallet_picks                                          │
│  • daily_wallet_summary                                      │
│  • wallet_stats_30d                                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ READ operations every 5 minutes
                           │ (sync.ts opens in readonly mode)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    SYNC SERVICE                              │
│                     (sync.ts)                                │
│                                                              │
│  1. Reads wallet data from tracker DB                       │
│  2. Calculates 7-day performance metrics                    │
│  3. Aggregates trade statistics                             │
│  4. Writes ONLY to dashboard DB                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ WRITE operations
                           │ (creates/updates dashboard data)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    DASHBOARD DATABASE                        │
│         (Created automatically by dashboard)                 │
│                                                              │
│  Location: /home/william/polymarket-wallet-dashboard/data/  │
│  File:     dashboard.db                                      │
│  Access:   READ/WRITE (managed by dashboard only)           │
│                                                              │
│  Tables:                                                     │
│  • wallet_dashboard_stats (PRIMARY KEY: wallet)             │
│                                                              │
│  Purpose:                                                    │
│  • Stores aggregated 7-day metrics per wallet               │
│  • Optimized for fast web dashboard queries                 │
│  • No duplicates (wallet address is unique)                 │
└─────────────────────────────────────────────────────────────┘
```

## Why Two Separate Databases?

### 1. **Data Isolation**
- Tracker database remains untouched by the dashboard
- Dashboard has its own optimized schema
- No risk of corrupting tracker data

### 2. **Performance**
- Dashboard database is optimized for web queries
- Pre-calculated metrics = faster API responses
- No complex joins needed at query time

### 3. **Independence**
- Dashboard can be stopped/started without affecting tracker
- Can delete and rebuild dashboard DB without losing tracker data
- Easy to reset dashboard data if needed

### 4. **Read-Only Tracker Access**
```typescript
// sync.ts opens tracker DB in read-only mode
this.trackerDb = new Database(trackerDbPath, { readonly: true });
```

## Database Paths

### Default Configuration

```env
# Tracker Database (READ-ONLY)
TRACKER_DB_PATH=/home/william/STRATEGIES/Polymarkets/data/tracker.db

# Dashboard Database (SEPARATE)
DASHBOARD_DB_PATH=/home/william/polymarket-wallet-dashboard/data/dashboard.db
```

### Custom Configuration

You can set any paths you want in `server/.env`:

```env
# Example: Both in same directory (still separate files!)
TRACKER_DB_PATH=/data/polymarket/tracker.db
DASHBOARD_DB_PATH=/data/polymarket/dashboard.db
```

## Schema Comparison

### Tracker DB Schema (from market_tracker.py)
```sql
-- Multiple tables with detailed trade history
markets
scan_events
market_positions
wallet_stats_7d          -- Snapshot-based stats
top_wallet_picks
daily_wallet_summary
wallet_stats_30d
```

### Dashboard DB Schema (new)
```sql
-- Single optimized table
wallet_dashboard_stats   -- Aggregated metrics per wallet
  ├── wallet (PRIMARY KEY)
  ├── profit_24h
  ├── recent_trade_*
  ├── avg_time_between_positions
  ├── win_rate
  ├── total_trades
  ├── avg_win / avg_loss
  ├── best_trade_amount
  └── ... (all metrics pre-calculated)
```

## Data Flow

```
market_tracker.py
    │
    │ Writes trade data
    ↓
tracker.db
    │
    │ Sync reads every 5 minutes (READ-ONLY)
    ↓
Sync Service (sync.ts)
    │ Calculates 7-day metrics
    │ Aggregates statistics
    │
    │ Writes aggregated data
    ↓
dashboard.db
    │
    │ Express API reads
    ↓
React Frontend
```

## Verification

When you start the server, you'll see:

```
[SERVER] Running on http://localhost:3001
[SERVER] ========================================
[SERVER] Tracker DB (READ-ONLY):   /home/william/STRATEGIES/Polymarkets/data/tracker.db
[SERVER] Dashboard DB (SEPARATE):  /home/william/polymarket-wallet-dashboard/data/dashboard.db
[SERVER] ========================================
[SERVER] NOTE: Dashboard uses its own separate database.
[SERVER]       Tracker database is never modified (read-only).
[SERVER] ========================================
```

## Safety Features

1. **Read-Only Mode**: Tracker DB is opened with `{ readonly: true }`
2. **Separate Connections**: Two different SQLite connections
3. **Error Isolation**: Dashboard DB errors won't affect tracker
4. **Easy Recovery**: Can delete dashboard DB and resync from tracker

## FAQs

### Can I delete the dashboard database?

Yes! It will be automatically recreated on next sync. All data comes from the tracker DB.

```bash
rm /home/william/polymarket-wallet-dashboard/data/dashboard.db
# Restart server - it will resync everything
```

### Will the dashboard modify my tracker database?

**NO.** The tracker database is opened in read-only mode. It's impossible for the dashboard to write to it.

### What happens if sync fails?

The dashboard will keep using the last successfully synced data. The tracker database is unaffected.

### Can I run multiple dashboards?

Yes! Each dashboard instance can have its own dashboard DB, all reading from the same tracker DB.

```env
# Dashboard Instance 1
DASHBOARD_DB_PATH=/path/to/dashboard1.db

# Dashboard Instance 2
DASHBOARD_DB_PATH=/path/to/dashboard2.db
```

## Troubleshooting

### "SQLITE_CANTOPEN: unable to open database"

**Cause**: Dashboard DB directory doesn't exist

**Fix**: The server creates it automatically, but you can also:
```bash
mkdir -p /home/william/polymarket-wallet-dashboard/data
```

### "SQLITE_READONLY: attempt to write a readonly database"

**Cause**: Dashboard DB file has wrong permissions

**Fix**:
```bash
chmod 644 /home/william/polymarket-wallet-dashboard/data/dashboard.db
```

### "No wallet data available"

**Cause**: Tracker DB is empty or path is wrong

**Fix**:
1. Verify tracker path in `.env`
2. Check that `market_tracker.py` has run and collected data
3. Manually sync: `curl -X POST http://localhost:3001/api/sync`

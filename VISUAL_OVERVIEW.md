# Visual Overview

## Database Separation Architecture

```
╔═══════════════════════════════════════════════════════════════════════╗
║                     POLYMARKET ECOSYSTEM                              ║
╚═══════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────┐
│                   EXISTING TRACKER SYSTEM                            │
│                  (market_tracker.py)                                 │
│                                                                      │
│  📂 /home/william/STRATEGIES/Polymarkets/                           │
│     └── data/                                                        │
│         └── tracker.db  ⚠️ READ-ONLY ACCESS FROM DASHBOARD         │
│                                                                      │
│  Tables in tracker.db:                                              │
│  ┌──────────────────┐                                               │
│  │ markets          │  Market metadata                              │
│  │ scan_events      │  Scan timestamps                              │
│  │ market_positions │  Position snapshots                           │
│  │ wallet_stats_7d  │  Wallet performance (7d)                      │
│  │ top_wallet_picks │  Top wallet rankings                          │
│  └──────────────────┘                                               │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            │  🔍 READ EVERY 5 MINUTES
                            │  (readonly: true)
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     SYNC SERVICE                                     │
│                    (server/src/sync.ts)                             │
│                                                                      │
│  Process:                                                            │
│  1️⃣  Query tracker.db for wallets (last 7 days)                    │
│  2️⃣  Calculate performance metrics:                                │
│      • 24h profit                                                    │
│      • Win rate                                                      │
│      • Avg trades per day                                            │
│      • Best/worst trades                                             │
│      • Profit factor                                                 │
│  3️⃣  Aggregate position data                                        │
│  4️⃣  Write to dashboard.db                                          │
│                                                                      │
│  Frequency: Every 5 minutes (automatic)                              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            │  ✍️ WRITE AGGREGATED DATA
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   NEW DASHBOARD DATABASE                             │
│                                                                      │
│  📂 /home/william/polymarket-wallet-dashboard/                      │
│     └── data/                                                        │
│         └── dashboard.db  ✅ CREATED & MANAGED BY DASHBOARD         │
│                                                                      │
│  Tables in dashboard.db:                                             │
│  ┌─────────────────────────┐                                        │
│  │ wallet_dashboard_stats  │  One row per unique wallet             │
│  │  • wallet (PK)          │  No duplicates                         │
│  │  • profit_24h           │  Pre-calculated metrics                │
│  │  • win_rate             │  Fast queries                          │
│  │  • total_trades         │  7-day window                          │
│  │  • best_trade_amount    │                                        │
│  │  • profit_factor        │                                        │
│  │  • ... (25+ fields)     │                                        │
│  └─────────────────────────┘                                        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            │  📡 API QUERIES
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     EXPRESS REST API                                 │
│                   (server/src/index.ts)                             │
│                                                                      │
│  Endpoints:                                                          │
│  ┌─────────────────────────────────────────┐                        │
│  │ GET  /api/wallets                       │                        │
│  │      ?sort=profit_24h&order=desc        │                        │
│  │                                          │                        │
│  │ GET  /api/wallets/:address              │                        │
│  │                                          │                        │
│  │ POST /api/sync (manual trigger)         │                        │
│  │                                          │                        │
│  │ GET  /api/health                        │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                      │
│  Auto-refresh: Syncs from tracker.db every 5 minutes                │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            │  🌐 HTTP REQUESTS
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND                                   │
│                   (client/src/App.tsx)                              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │                    MOBILE VIEW                          │        │
│  ├─────────────────────────────────────────────────────────┤        │
│  │  🟢 XA    0xea7a...eab1         Next: 22m              │        │
│  │           $1,136.2                                      │        │
│  │           Bitcoin (up/dn)                               │        │
│  │           1h ago                                        │        │
│  │           $8.4                  [StakeBet]              │        │
│  ├─────────────────────────────────────────────────────────┤        │
│  │  Track Record (scroll →)                               │        │
│  │  81% | 60/day | $22 | -$16 | $138 | $1,305 | ...      │        │
│  │  421  |  5m    |     |      | 23h  | -$161  | ...      │        │
│  └─────────────────────────────────────────────────────────┘        │
│                                                                      │
│  Features:                                                           │
│  • Auto-refresh every 5 minutes                                     │
│  • Click wallet to copy                                              │
│  • Sort by profit, win rate, etc.                                   │
│  • Horizontal scroll for metrics                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## File Organization

```
polymarket-wallet-dashboard/
│
├── 📄 Documentation
│   ├── README.md                  Complete guide
│   ├── QUICKSTART.md             5-minute setup
│   ├── DATABASE_ARCHITECTURE.md   Database details
│   ├── PROJECT_STRUCTURE.md       Code organization
│   ├── SUMMARY.md                 Executive summary
│   └── VISUAL_OVERVIEW.md         This file
│
├── 🔧 Configuration
│   ├── .gitignore                 Git ignore rules
│   └── setup.sh                   Auto-install script
│
├── 🖥️ Backend (server/)
│   ├── package.json               Dependencies
│   ├── tsconfig.json              TypeScript config
│   ├── .env.example               Config template
│   └── src/
│       ├── index.ts               🚀 Main server
│       ├── db.ts                  💾 Dashboard DB
│       ├── sync.ts                🔄 Sync service
│       ├── types.ts               📝 Interfaces
│       └── routes/
│           └── wallets.ts         🛣️ API routes
│
└── 🎨 Frontend (client/)
    ├── package.json               Dependencies
    ├── vite.config.ts             Build config
    ├── tailwind.config.js         CSS config
    ├── index.html                 Entry point
    └── src/
        ├── main.tsx               🚀 React entry
        ├── App.tsx                📱 Main app
        ├── index.css              🎨 Global styles
        ├── types.ts               📝 Interfaces
        ├── hooks/
        │   └── useWallets.ts      🪝 Data fetching
        └── components/
            ├── WalletCard.tsx     📇 Today section
            ├── WalletAddress.tsx  📋 Copy address
            ├── TrackRecord.tsx    📊 Metrics
            └── SortFilter.tsx     🔽 Sorting
```

## Data Update Flow

```
⏰ Every 5 Minutes:

1. 🔄 Sync Trigger
   └─> sync.ts wakes up

2. 🔍 Read Tracker DB (READ-ONLY)
   └─> SELECT wallets, positions, stats
   └─> FROM tracker.db
   └─> WHERE last 7 days

3. 🧮 Calculate Metrics
   ├─> 24h profit
   ├─> Win rate (7d)
   ├─> Avg trades/day
   ├─> Best/worst trades
   ├─> Profit factor
   └─> Time between positions

4. ✍️ Write Dashboard DB
   └─> INSERT OR REPLACE INTO wallet_dashboard_stats
   └─> Prevents duplicates (wallet = PRIMARY KEY)

5. 📡 API Ready
   └─> Fresh data available at /api/wallets

6. 🌐 Frontend Auto-Refresh
   └─> useWallets hook fetches new data
   └─> UI updates automatically
```

## Component Tree

```
<App>
  │
  ├── <header>
  │   ├── Title: "Polymarket Wallet Tracker"
  │   └── Status: "X wallets • Auto-refresh 5m"
  │
  ├── <SortFilter>
  │   ├── Sort dropdown
  │   └── Order toggle (asc/desc)
  │
  └── For each wallet:
      │
      ├── <div "Today">
      │   └── <WalletCard>
      │       ├── Badge (random color)
      │       ├── <WalletAddress> (click to copy)
      │       ├── 24h Profit (green/red)
      │       ├── Recent trade info
      │       ├── Recent P&L
      │       ├── Next trade countdown
      │       └── StakeBet button
      │
      └── <div "Track Record">
          └── <TrackRecord>
              ├── Win rate & trades
              ├── Trades/day & hold time
              ├── Avg win/loss
              ├── Best/worst trades
              ├── # wins/losses
              ├── Avg trade size
              └── Profit factor
```

## Safety Guarantees

```
✅ Tracker DB is NEVER modified
   └─> Opened with { readonly: true }

✅ No data loss risk
   └─> Dashboard DB can be deleted & rebuilt

✅ Independent operation
   └─> Dashboard won't affect tracker

✅ No duplicates
   └─> wallet = PRIMARY KEY

✅ Error isolation
   └─> Dashboard errors don't affect tracker

✅ Easy recovery
   └─> Delete dashboard.db, resync from tracker
```

## Performance

```
Backend (Node.js):
├─> SQLite with WAL mode
├─> Indexed queries (profit_24h, win_rate)
├─> Pre-calculated metrics
└─> Fast API responses (<10ms)

Frontend (React):
├─> Vite dev server (fast HMR)
├─> Tailwind CSS (optimized)
├─> Auto-refresh (5 min intervals)
└─> Mobile-first (optimized layout)

Database:
├─> Single table for dashboard
├─> No complex joins at query time
├─> Optimized for reads
└─> Automatic sync (no manual refresh)
```

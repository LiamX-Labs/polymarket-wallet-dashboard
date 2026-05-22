# Project Summary

## Polymarket Wallet Dashboard

A mobile-first web dashboard for tracking Polymarket wallet performance with **completely separate database architecture**.

---

## Key Architecture Points

### ✅ Two Separate Databases

```
tracker.db (READ-ONLY)  →  Sync Service  →  dashboard.db (SEPARATE)
     ↑                                              ↓
market_tracker.py                            Web Dashboard
```

1. **Tracker Database** (`tracker.db`)
   - Location: `/home/william/STRATEGIES/Polymarkets/data/tracker.db`
   - Created and managed by `market_tracker.py`
   - **Opened in READ-ONLY mode** by dashboard
   - **NEVER modified** by the dashboard

2. **Dashboard Database** (`dashboard.db`)
   - Location: `/home/william/polymarket-wallet-dashboard/data/dashboard.db`
   - Created automatically by the dashboard
   - Contains pre-calculated 7-day metrics
   - Can be deleted and rebuilt anytime

### ✅ Data Flow

```
1. market_tracker.py writes to tracker.db
2. Dashboard sync service READS from tracker.db (every 5 min)
3. Sync service calculates 7-day metrics
4. Sync service WRITES to dashboard.db
5. API queries dashboard.db
6. React frontend displays data
```

---

## Project Structure

```
polymarket-wallet-dashboard/
├── server/                    # Backend (Express + TypeScript)
│   ├── src/
│   │   ├── index.ts          # Server + auto-sync
│   │   ├── db.ts             # Dashboard DB operations
│   │   ├── sync.ts           # Reads tracker DB (READ-ONLY)
│   │   └── routes/           # API endpoints
│   └── package.json
│
├── client/                    # Frontend (React + Tailwind)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/       # UI components
│   │   └── hooks/            # Data fetching
│   └── package.json
│
├── README.md                  # Full documentation
├── QUICKSTART.md             # 5-minute setup guide
├── DATABASE_ARCHITECTURE.md   # Database details
└── PROJECT_STRUCTURE.md       # Code organization
```

---

## Features Implemented

### Backend
- ✅ Express REST API
- ✅ Two separate SQLite databases
- ✅ Auto-sync every 5 minutes
- ✅ Read-only access to tracker DB
- ✅ 7-day performance calculations
- ✅ Unique wallet constraint (no duplicates)
- ✅ Sorting by multiple fields
- ✅ Error handling and logging

### Frontend
- ✅ Mobile-first responsive design
- ✅ Auto-refresh every 5 minutes
- ✅ Dark theme
- ✅ Fixed "Today" section
- ✅ Horizontally scrollable "Track Record"
- ✅ Click-to-reveal wallet addresses
- ✅ Copy to clipboard functionality
- ✅ Sortable data (profit, win rate, etc.)
- ✅ Loading and error states

### UI Components (matching screenshot)

**Today Section**:
- ✅ Random color badges (XA, XC, XE, etc.)
- ✅ Clickable wallet address
- ✅ 24h profit (green/red)
- ✅ Recent trade info
- ✅ Recent trade P&L
- ✅ Next trade countdown
- ✅ StakeBet button (placeholder)

**Track Record**:
- ✅ Win rate & trade count
- ✅ Trades per day & hold time
- ✅ Avg win/loss amounts
- ✅ Best/worst trades with timestamps
- ✅ Number of wins/losses
- ✅ Average trade size
- ✅ Profit factor

---

## Quick Start

### 1. Install Dependencies
```bash
cd /home/william/polymarket-wallet-dashboard
./setup.sh
```

### 2. Configure
```bash
cd server
cp .env.example .env
nano .env  # Set TRACKER_DB_PATH
```

### 3. Run
```bash
# Terminal 1
cd server && npm run dev

# Terminal 2
cd client && npm run dev
```

### 4. Access
```
http://localhost:3000
```

---

## API Endpoints

```
GET  /api/wallets              # Get all wallets (sortable)
GET  /api/wallets/:address     # Get specific wallet
POST /api/sync                 # Manual sync trigger
GET  /api/health               # Health check
```

---

## Database Safety

### Read-Only Tracker Access
```typescript
// sync.ts - Line 10
this.trackerDb = new Database(trackerDbPath, { readonly: true });
```

### Verification on Startup
```
[SERVER] ========================================
[SERVER] Tracker DB (READ-ONLY):   /path/to/tracker.db
[SERVER] Dashboard DB (SEPARATE):  /path/to/dashboard.db
[SERVER] ========================================
[SERVER] NOTE: Dashboard uses its own separate database.
[SERVER]       Tracker database is never modified (read-only).
[SERVER] ========================================
```

---

## Technology Stack

**Backend**:
- Node.js + TypeScript
- Express (REST API)
- better-sqlite3 (SQLite driver)
- CORS, dotenv

**Frontend**:
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS
- Custom hooks for data fetching

---

## Documentation Files

1. **[README.md](README.md)** - Complete documentation
   - Architecture overview
   - Setup instructions
   - API reference
   - Database schema
   - Troubleshooting

2. **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup
   - Quick installation
   - Basic configuration
   - Running the app
   - Common issues

3. **[DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md)** - Database details
   - Two-database architecture
   - Data flow diagrams
   - Schema comparison
   - Safety features
   - FAQs

4. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Code organization
   - File structure
   - Component descriptions
   - Data flow
   - Development workflow

---

## Next Steps

### To Run the Dashboard:

1. **Ensure tracker is running**:
   ```bash
   # In your Polymarkets directory
   python scripts/market_tracker.py
   ```

2. **Start the dashboard**:
   ```bash
   cd /home/william/polymarket-wallet-dashboard
   ./setup.sh  # First time only

   # Terminal 1
   cd server && npm run dev

   # Terminal 2
   cd client && npm run dev
   ```

3. **Access**: http://localhost:3000

### To Verify Database Separation:

```bash
# Check that tracker DB exists
ls -lh /home/william/STRATEGIES/Polymarkets/data/tracker.db

# Dashboard DB will be created on first sync
ls -lh /home/william/polymarket-wallet-dashboard/data/dashboard.db
```

---

## Important Notes

1. **No Data Loss Risk**: Tracker database is read-only
2. **Independent Operation**: Dashboard can stop/start without affecting tracker
3. **Easy Recovery**: Delete dashboard.db and resync from tracker
4. **No Duplicates**: Wallet address is PRIMARY KEY in dashboard DB
5. **7-Day Window**: All metrics calculated from last 7 days only

---

## Support

- Check server logs for sync errors
- Check browser console for frontend errors
- Review documentation files for detailed info
- Verify database paths in `server/.env`

## Future Enhancements

- [ ] Historical performance charts
- [ ] Wallet comparison view
- [ ] Custom date ranges
- [ ] Export to CSV
- [ ] WebSocket real-time updates
- [ ] Push notifications
- [ ] StakeBet integration

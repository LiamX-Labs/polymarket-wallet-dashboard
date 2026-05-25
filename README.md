# Polymarket Wallet Dashboard

Real-time dashboard for tracking Polymarket wallet performance and trading activity with **integrated market tracker**.

## Features

- **Live Wallet Tracking**: Monitor multiple wallets with auto-refresh every 5 minutes
- **Comprehensive Stats**: Win rate, profit/loss, trade frequency, and more
- **Built-in Market Tracker**: Integrated Python tracker runs locally (no external dependencies)
- **Mobile-First Design**: Responsive layout with horizontal scrolling for detailed metrics
- **Sortable Metrics**: Sort by profit, win rate, trade count, etc.
- **Click-to-Copy Addresses**: Easy wallet address management

## Architecture

The dashboard consists of three main components:

1. **Market Tracker** (`tracker/`) - Python-based tracker that monitors Polymarket markets and wallets
2. **Backend Server** (`server/`) - Node.js/Express API that syncs data from tracker to dashboard
3. **Frontend** (`client/`) - React/TypeScript dashboard UI

### Database Structure

- **tracker.sqlite3** (READ-ONLY by server) - Created by market tracker, contains raw market data
- **dashboard.db** (SEPARATE) - Dashboard-specific database synced from tracker every 5 minutes

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+
- npm or yarn
- PM2 (recommended for process management)

### Installation

1. **Install dependencies**:

```bash
# Install Python dependencies
pip install python-dotenv aiohttp requests

# Install Node.js dependencies
cd server && npm install
cd ../client && npm install
cd ..
```

2. **Start all services with PM2** (Recommended):

```bash
# Install PM2 globally if not already installed
npm install -g pm2

# Start all services (tracker + server + client)
pm2 start ecosystem.config.js

# Check status
pm2 status

# View logs
pm2 logs
```

3. **Access the dashboard**: Open http://localhost:5173 in your browser

### Manual Start (Alternative)

If you prefer to run services manually in separate terminals:

```bash
# Terminal 1: Start market tracker
./run-tracker.sh

# Terminal 2: Start backend server
cd server && npm run dev

# Terminal 3: Start frontend
cd client && npm run dev
```

## API Endpoints

### `GET /api/wallets`
Get all tracked wallets with optional sorting

**Query Parameters:**
- `sort`: Field to sort by (default: `profit_24h`)
  - Options: `profit_24h`, `win_rate`, `total_trades`, `profit_factor`, `best_trade_amount`
- `order`: Sort order (default: `desc`)
  - Options: `asc`, `desc`

**Example:**
```bash
curl "http://localhost:3001/api/wallets?sort=win_rate&order=desc"
```

### `GET /api/wallets/:address`
Get specific wallet details by address

**Example:**
```bash
curl "http://localhost:3001/api/wallets/0xea7a...eab1"
```

### `POST /api/sync`
Manually trigger a sync from tracker database

**Example:**
```bash
curl -X POST "http://localhost:3001/api/sync"
```

### `GET /api/health`
Health check endpoint

## Database Schema

### `wallet_dashboard_stats` Table

| Field | Type | Description |
|-------|------|-------------|
| `wallet` | TEXT | Wallet address (PRIMARY KEY) |
| **Today Metrics (24h)** | | |
| `profit_24h` | REAL | Profit in last 24 hours |
| `recent_trade_market` | TEXT | Most recent market traded |
| `recent_trade_side` | TEXT | UP or DOWN |
| `recent_trade_timestamp` | INTEGER | Unix timestamp |
| `recent_trade_pnl` | REAL | P&L of recent trade |
| `avg_time_between_positions` | INTEGER | Avg seconds between trades |
| `last_position_timestamp` | INTEGER | Last trade timestamp |
| **Track Record (7 days)** | | |
| `win_rate` | REAL | Percentage of winning trades |
| `total_trades` | INTEGER | Total trades in 7 days |
| `avg_trades_per_day` | REAL | Average trades per day |
| `avg_hold_time_seconds` | INTEGER | Average position duration |
| `avg_win` | REAL | Average winning trade amount |
| `avg_loss` | REAL | Average losing trade amount |
| `best_trade_amount` | REAL | Largest profit |
| `best_trade_time_ago` | INTEGER | Timestamp of best trade |
| `worst_perf_amount` | REAL | Worst loss |
| `num_wins` | INTEGER | Count of wins |
| `num_losses` | INTEGER | Count of losses |
| `avg_trade_size` | REAL | Average position size |
| `profit_factor` | REAL | Total wins / Total losses |
| `last_updated` | INTEGER | Last sync timestamp |

## UI Components

### Today Section (Left Panel)
- Circular wallet badge (random color)
- Clickable wallet address
- 24h profit (green/red)
- Recent trade info
- Recent trade P&L
- Next trade countdown
- StakeBet button (placeholder)

### Track Record Section (Right Panel - Scrollable)
- Win rate & trade count
- Trades per day & hold time
- Average win/loss
- Best/worst trades with timestamps
- Number of wins/losses
- Average trade size
- Profit factor

## Configuration

### Tracker Settings (.env.tracker)

The market tracker configuration (no Telegram notifications for dashboard):

- `TRACKER_POLL_INTERVAL_SECONDS`: How often to poll markets (default: 15s)
- `TRACKER_DATABASE_PATH`: Path to tracker database (auto-set)
- `TRACKER_DRY_RUN`: Always true for dashboard (no Telegram notifications)

### Server Settings (server/.env)

- `PORT`: Server port (default: 3001)
- `TRACKER_DB_PATH`: Path to tracker database (READ-ONLY)
- `DASHBOARD_DB_PATH`: Path to dashboard database

## PM2 Management

```bash
# Start all services
pm2 start ecosystem.config.js

# Stop all services
pm2 stop all

# Restart all services
pm2 restart all

# Delete all services
pm2 delete all

# View logs for specific service
pm2 logs polymarket-tracker
pm2 logs polymarket-dashboard-server
pm2 logs polymarket-dashboard-client

# Monitor resources
pm2 monit

# Save PM2 configuration to restart on boot
pm2 save
pm2 startup
```

## Project Structure

```
polymarket-wallet-dashboard/
├── bot/                    # Bot utilities (analysis, formatting)
├── tracker/                # Market tracker module
│   ├── clob_client.py     # CLOB API client
│   ├── gamma_client.py    # Gamma API client
│   ├── market_tracker.py  # Main tracker logic
│   ├── tracker_db.py      # Database operations
│   └── wallet_profiler.py # Wallet analysis
├── server/                 # Backend API
│   ├── src/
│   │   ├── db.ts          # Dashboard database
│   │   ├── sync.ts        # Sync service
│   │   └── routes/        # API endpoints
│   └── .env               # Server config
├── client/                 # Frontend React app
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── hooks/         # React hooks
│   │   └── types.ts       # TypeScript types
│   └── index.html
├── data/                   # Databases (auto-created)
│   ├── tracker.sqlite3    # Tracker DB (READ-ONLY by server)
│   └── dashboard.db       # Dashboard DB
├── logs/                   # PM2 logs
├── .env.tracker           # Tracker configuration
├── market_tracker.py      # Tracker entrypoint
├── run-tracker.sh         # Tracker runner script
└── ecosystem.config.js    # PM2 configuration
```

## Troubleshooting

### Tracker not syncing data

```bash
# Check tracker logs
pm2 logs polymarket-tracker

# Restart tracker
pm2 restart polymarket-tracker

# Check database was created
ls -la data/tracker.sqlite3
```

### Server can't read tracker database

```bash
# Check database exists and has data
sqlite3 data/tracker.sqlite3 "SELECT COUNT(*) FROM wallet_stats_7d;"

# Check server logs
pm2 logs polymarket-dashboard-server

# Manually trigger sync
curl -X POST http://localhost:3001/api/sync
```

### Frontend not updating

```bash
# Check if server is running
curl http://localhost:3001/api/wallets

# Check browser console for errors
# Verify auto-refresh is working (every 5 minutes)

# Restart client
pm2 restart polymarket-dashboard-client
```

### No wallets showing

- Wait for tracker to collect data (may take 15-30 minutes initially)
- Check tracker logs: `pm2 logs polymarket-tracker`
- Verify tracker is polling markets successfully
- Manually trigger sync: `curl -X POST http://localhost:3001/api/sync`

## Deployment

### Deploy to Render.com (Free)

This project includes a `render.yaml` blueprint for one-click deployment:

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Deploy to Render"
   git push origin main
   ```

2. **Deploy to Render:**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click **"New"** → **"Blueprint"**
   - Connect your GitHub repository
   - Render will auto-create all 3 services (tracker, API, frontend)

3. **Access your dashboard:**
   - Find your static site URL in Render dashboard
   - Example: `https://polymarket-dashboard-client.onrender.com`

**Full deployment guide:** See [DEPLOY.md](./DEPLOY.md) for detailed instructions, environment variables, and troubleshooting.

**Other hosting options:**
- Railway.app (Easy PostgreSQL integration)
- Fly.io (3 free VMs)
- Vercel (frontend) + Render (backend + tracker)

## Future Enhancements

- [ ] Historical performance charts
- [ ] Wallet comparison view
- [ ] Custom date range filtering
- [ ] Export data to CSV
- [ ] Real-time WebSocket updates
- [ ] Push notifications for top wallets
- [ ] StakeBet integration

## License

MIT

# Quick Start Guide

## Start All Services with PM2

```bash
cd /home/william/polymarket-wallet-dashboard

# Start all services (tracker + server + client)
pm2 start ecosystem.config.js

# Check status
pm2 status

# View logs
pm2 logs
```

## Access the Dashboard

Open http://localhost:5173 in your browser

## Monitor Services

```bash
# View specific service logs
pm2 logs polymarket-tracker
pm2 logs polymarket-dashboard-server
pm2 logs polymarket-dashboard-client

# Real-time monitoring
pm2 monit

# Restart a service
pm2 restart polymarket-tracker
```

## Stop All Services

```bash
pm2 stop all
# or
pm2 delete all
```

## What's Running

1. **Polymarket Tracker** (Python)
   - Monitors Polymarket markets
   - Writes data to `data/tracker.sqlite3`
   - Runs every 15 seconds
   - No Telegram notifications

2. **Dashboard Server** (Node.js)
   - API server on port 3001
   - Syncs from tracker DB to dashboard DB every 5 minutes
   - Provides `/api/wallets` endpoint

3. **Dashboard Client** (React)
   - Web UI on port 5173
   - Auto-refreshes every 5 minutes
   - Mobile-first responsive design

## Initial Setup

The tracker needs time to collect data (15-30 minutes). You can monitor progress:

```bash
# Watch tracker logs
pm2 logs polymarket-tracker --lines 100

# Check database size
ls -lh data/tracker.sqlite3

# Check wallet count in database
sqlite3 data/tracker.sqlite3 "SELECT COUNT(DISTINCT wallet) FROM wallet_stats_7d;"
```

## Troubleshooting

### No wallets showing in dashboard

1. Wait 15-30 minutes for tracker to collect data
2. Check tracker is running: `pm2 status`
3. Check tracker logs: `pm2 logs polymarket-tracker`
4. Manually trigger sync: `curl -X POST http://localhost:3001/api/sync`

### Tracker won't start

1. Check Python environment: `/home/william/anaconda3/bin/python --version`
2. Check logs: `pm2 logs polymarket-tracker`
3. Verify conda packages: `conda list | grep -E "(dotenv|aiohttp|requests)"`

### Server errors

1. Check server logs: `pm2 logs polymarket-dashboard-server`
2. Verify database exists: `ls -la data/tracker.sqlite3`
3. Test API: `curl http://localhost:3001/api/health`

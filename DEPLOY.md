# Deployment Guide - Render.com

This guide will help you deploy the Polymarket Wallet Dashboard to Render.com's free tier.

## Prerequisites

- GitHub account with this repository pushed
- Render.com account (sign up at https://render.com)
- GitHub linked to Render account

## Deployment Steps

### 1. Push to GitHub

First, ensure your code is on GitHub:

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### 2. Deploy to Render

#### Option A: Using Blueprint (Recommended - One Click)

1. Go to https://dashboard.render.com/
2. Click **"New"** → **"Blueprint"**
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml` and create all 3 services:
   - `polymarket-tracker` (Background Worker)
   - `polymarket-dashboard-api` (Web Service)
   - `polymarket-dashboard-client` (Static Site)

#### Option B: Manual Setup (If Blueprint Doesn't Work)

**Service 1: Python Tracker (Background Worker)**
1. Click **"New"** → **"Background Worker"**
2. Connect your repository
3. Configure:
   - **Name:** `polymarket-tracker`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python market_tracker.py`
   - **Plan:** `Free`
4. Add Disk:
   - Click **"Add Disk"**
   - **Name:** `tracker-data`
   - **Mount Path:** `/var/data`
   - **Size:** `1 GB`
5. Add Environment Variables (see section below)
6. Click **"Create Background Worker"**

**Service 2: Backend API (Web Service)**
1. Click **"New"** → **"Web Service"**
2. Connect your repository
3. Configure:
   - **Name:** `polymarket-dashboard-api`
   - **Runtime:** `Node`
   - **Build Command:** `cd server && npm install && npm run build`
   - **Start Command:** `cd server && npm start`
   - **Plan:** `Free`
4. Add Same Disk (Important - must share with tracker):
   - Click **"Add Disk"**
   - **Name:** `tracker-data` (same name as tracker)
   - **Mount Path:** `/var/data`
   - **Size:** `1 GB`
5. Add Environment Variables (see section below)
6. Click **"Create Web Service"**

**Service 3: Frontend (Static Site)**
1. Click **"New"** → **"Static Site"**
2. Connect your repository
3. Configure:
   - **Name:** `polymarket-dashboard-client`
   - **Build Command:** `cd client && npm install && npm run build`
   - **Publish Directory:** `./client/dist`
   - **Plan:** `Free`
4. Add Environment Variable:
   - **Key:** `VITE_API_URL`
   - **Value:** Your API service URL (e.g., `https://polymarket-dashboard-api.onrender.com`)
5. Add Redirect/Rewrite Rule:
   - **Source:** `/*`
   - **Destination:** `/index.html`
   - **Action:** `Rewrite`
6. Click **"Create Static Site"**

### 3. Environment Variables

#### Tracker Service (polymarket-tracker)

```
TRACKER_POLL_INTERVAL_SECONDS=15
TRACKER_TRIGGER_TOLERANCE_SECONDS=20
TRACKER_DATABASE_PATH=/var/data/tracker.sqlite3
TRACKER_DAILY_REPORT_HOUR_UTC=23
TRACKER_DRY_RUN=true
GAMMA_API_BASE_URL=https://gamma-api.polymarket.com
CLOB_API_BASE_URL=https://clob.polymarket.com
```

Optional (if you want Telegram notifications):
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TRACKER_TELEGRAM_CHAT_ID=your_chat_id_here
```

#### API Service (polymarket-dashboard-api)

```
PORT=10000
TRACKER_DB_PATH=/var/data/tracker.sqlite3
DASHBOARD_DB_PATH=/var/data/dashboard.db
NODE_ENV=production
```

#### Frontend (polymarket-dashboard-client)

```
VITE_API_URL=https://your-api-service-url.onrender.com
```

Replace `your-api-service-url` with the actual URL of your API service (found in Render dashboard).

### 4. Verify Deployment

1. **Check Tracker Logs:**
   - Go to `polymarket-tracker` service
   - Click **"Logs"**
   - You should see: "Starting market tracker..."

2. **Check API:**
   - Go to `polymarket-dashboard-api` service
   - Copy the URL (e.g., `https://polymarket-dashboard-api.onrender.com`)
   - Visit: `https://polymarket-dashboard-api.onrender.com/api/health`
   - Should return: `{"status":"ok"}`

3. **Check Frontend:**
   - Go to `polymarket-dashboard-client` service
   - Copy the URL
   - Visit the URL in your browser
   - Dashboard should load (may take 15-30 min for initial data)

## Important Notes

### Free Tier Limitations

1. **Sleep Mode:** Free web services sleep after 15 minutes of inactivity
   - First request after sleep takes ~30 seconds (cold start)
   - Background workers stay running 24/7

2. **Shared Disk:** Both tracker and API must use the SAME disk
   - Use identical disk name: `tracker-data`
   - This allows the API to read the tracker's database

3. **Build Time:** Free builds can take 5-10 minutes

### Database Persistence

The `/var/data` disk is persistent and shared between tracker and API:
- `tracker.sqlite3` - Created by tracker (READ-ONLY by API)
- `dashboard.db` - Created by API (synced from tracker)

### Auto-Deploy

Once set up, Render automatically redeploys when you push to GitHub:

```bash
git add .
git commit -m "Update feature"
git push origin main
```

All services will rebuild and redeploy automatically.

## Troubleshooting

### Tracker Not Starting
- Check logs for Python errors
- Verify `requirements.txt` exists
- Ensure environment variables are set

### API Can't Read Tracker Database
- Verify BOTH services use the same disk name (`tracker-data`)
- Check that `TRACKER_DB_PATH` matches tracker's `TRACKER_DATABASE_PATH`
- Wait 5-10 minutes for tracker to create initial data

### Frontend Shows Errors
- Check that `VITE_API_URL` points to correct API service URL
- Verify API is running: visit `/api/health` endpoint
- Check browser console for CORS errors

### Cold Starts (Free Tier)
- First request after 15 min of inactivity takes ~30 seconds
- Consider upgrading to paid tier ($7/month) to eliminate sleep mode

## Monitoring

### View Logs
```
1. Go to Render Dashboard
2. Click on service name
3. Click "Logs" tab
4. Real-time logs appear here
```

### Check Database
You can SSH into services to inspect databases:

```bash
# In Render dashboard, click "Shell" tab
sqlite3 /var/data/tracker.sqlite3
.tables
SELECT COUNT(*) FROM wallet_stats_7d;
.quit
```

## Upgrading

To move from free to paid tier (eliminates sleep mode):

1. Go to service in Render dashboard
2. Click **"Settings"**
3. Under **"Instance Type"**, select **"Starter"** ($7/month)
4. Click **"Save Changes"**

## Custom Domain (Optional)

To use your own domain:

1. Go to `polymarket-dashboard-client` service
2. Click **"Settings"** → **"Custom Domain"**
3. Add your domain
4. Update DNS records as instructed
5. Render provides free SSL certificates

## Cost Estimate

**Free Tier:**
- 3 services: $0/month
- 1GB disk: $0/month
- 750 hours/month free compute
- **Total: $0/month**

**Paid Tier (No Sleep):**
- Background Worker: $7/month
- Web Service: $7/month
- Static Site: $0/month
- 1GB disk: $0.25/month
- **Total: ~$14.25/month**

## Support

- Render Documentation: https://render.com/docs
- This Project Issues: Create issue in GitHub repo

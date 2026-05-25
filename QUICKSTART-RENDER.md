# Quick Start: Deploy to Render in 5 Minutes

## Step 1: Push to GitHub

```bash
# Make sure you're in the project directory
cd /home/william/polymarket-wallet-dashboard

# Add all files
git add .

# Commit
git commit -m "Add Render deployment configuration"

# Push to GitHub (replace 'main' with your branch name if different)
git push origin main
```

## Step 2: Deploy to Render

1. **Go to Render Dashboard**
   - Visit: https://dashboard.render.com/
   - Sign in (GitHub already linked ✓)

2. **Create New Blueprint**
   - Click **"New"** button (top right)
   - Select **"Blueprint"**
   - Click **"Connect repository"**
   - Find and select: `polymarket-wallet-dashboard`
   - Click **"Connect"**

3. **Render Auto-Configuration**
   - Render will detect `render.yaml`
   - You'll see 3 services listed:
     - ✓ polymarket-tracker (Background Worker)
     - ✓ polymarket-dashboard-api (Web Service)
     - ✓ polymarket-dashboard-client (Static Site)
   - Click **"Apply"**

4. **Wait for Deployment**
   - All 3 services will start building (5-10 minutes)
   - You can watch logs in real-time
   - Green checkmarks = deployed successfully

## Step 3: Configure Frontend API URL

Once the API is deployed:

1. **Get API URL:**
   - Click on `polymarket-dashboard-api` service
   - Copy the URL (e.g., `https://polymarket-dashboard-api.onrender.com`)

2. **Update Frontend:**
   - Click on `polymarket-dashboard-client` service
   - Go to **"Environment"** tab
   - Find `VITE_API_URL` variable
   - Paste your API URL
   - Click **"Save Changes"**
   - Frontend will auto-rebuild

## Step 4: Access Your Dashboard

1. **Get Frontend URL:**
   - Click on `polymarket-dashboard-client` service
   - Copy the URL (e.g., `https://polymarket-dashboard-client.onrender.com`)
   - Open in browser

2. **Wait for Data:**
   - First load may take 30 seconds (cold start)
   - Initial data collection takes 15-30 minutes
   - Dashboard auto-refreshes every 5 minutes

## That's It! 🎉

Your dashboard is now live and running 24/7 for free.

## Quick Health Checks

**Check Tracker:**
```
Service: polymarket-tracker → Logs
Should see: "Starting market tracker..."
```

**Check API:**
```
Visit: https://your-api-url.onrender.com/api/health
Should see: {"status":"ok"}
```

**Check Frontend:**
```
Visit: https://your-frontend-url.onrender.com
Should see: Dashboard UI
```

## Common Issues

**"No wallets showing"**
- Wait 15-30 minutes for initial data collection
- Check tracker logs for errors

**"API error" in frontend**
- Verify VITE_API_URL is set correctly
- Check API service is running (green status)

**"Cold start taking long"**
- Normal for free tier (first request after 15 min idle)
- Takes ~30 seconds
- Upgrade to paid tier ($7/mo) to eliminate

## Need Help?

See [DEPLOY.md](./DEPLOY.md) for detailed troubleshooting and advanced configuration.

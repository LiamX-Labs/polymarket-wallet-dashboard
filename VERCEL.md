# Deployment Guide — Vercel + PostgreSQL (disabled)

> **Status:** Vercel deployment is kept in the repo but **disabled by default**.
> Rename `vercel.json.disabled` → `vercel.json` to re-enable.
> **Primary deployment is Render** — see `render.yaml`.

Deploy the Polymarket Wallet Dashboard frontend and API to Vercel with **Postgres (Neon)** for persistent storage.

## Architecture

| Component | Where it runs | Database |
|-----------|---------------|----------|
| React frontend | Vercel (static) | — |
| Express API | Vercel (serverless) | Vercel Postgres |
| Python tracker | Render / Railway / VPS | SQLite locally + mirrors to Postgres |

Vercel serverless functions are ephemeral — local SQLite files do not work. The API automatically uses PostgreSQL (via the Neon serverless driver) when `POSTGRES_URL` is set.

---

## 1. Create Vercel Postgres

1. Open your Vercel project → **Storage** → **Create Database** → **Postgres** (Neon).
2. Connect the database to your project. Vercel injects:
   - `POSTGRES_URL`
   - `POSTGRES_PRISMA_URL`
   - `POSTGRES_URL_NON_POOLING`

Tables are created automatically on first API request. You can also run the schema manually:

```bash
psql "$POSTGRES_URL" -f sql/postgres-schema.sql
```

---

## 2. Environment Variables

Set these in **Vercel → Project → Settings → Environment Variables**:

| Variable | Value | Required |
|----------|-------|----------|
| `POSTGRES_URL` | Auto-injected by Vercel Postgres | Yes |
| `CORS_ORIGIN` | `https://your-app.vercel.app` or `*` | Yes |
| `NODE_ENV` | `production` | Yes |

For the **frontend build**, leave `VITE_API_URL` empty so the client calls `/api` on the same domain.

---

## 3. Deploy

1. Push the repo to GitHub and import it in Vercel.
2. Set **Root Directory** to the repository root.
3. Vercel reads `vercel.json`:
   - Builds the React client → `client/dist`
   - Routes `/api/*` to the Express serverless function at `api/index.ts`
4. Add Vercel Postgres and redeploy.

---

## 4. Run the Python Tracker (separate host)

The tracker is a long-running process and cannot run on Vercel. Run it on Render, Railway, Fly.io, or a VPS.

Set `POSTGRES_URL` on the tracker host so it mirrors `wallet_dashboard_summary` to the same Postgres database:

```env
POSTGRES_URL=postgres://...   # Same URL as Vercel
TRACKER_DATABASE_PATH=./data/tracker.sqlite3
TRACKER_DRY_RUN=true
```

```bash
pip install -r requirements.txt
python market_tracker.py
```

Data flow:

```
market_tracker.py → SQLite (local) + PostgreSQL (wallet_dashboard_summary)
                                              ↓
Vercel API sync   → PostgreSQL (wallet_dashboard_stats)
                                              ↓
React frontend    → GET /api/wallets
```

Trigger a manual sync after tracker data arrives:

```bash
curl -X POST https://your-app.vercel.app/api/sync
```

---

## 5. Local Development

**SQLite (default)** — no Postgres URL needed:

```bash
cd server && cp .env.example .env
npm run dev          # from server/
cd client && npm run dev
```

**PostgreSQL locally** — set `POSTGRES_URL` in `server/.env`:

```bash
POSTGRES_URL=postgres://localhost:5432/polymarket
```

---

## 6. Useful Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/wallets` | Wallet list |
| `GET /api/debug` | Sync / DB status |
| `POST /api/sync` | Manual sync from Postgres summary → stats |

---

## Troubleshooting

**Empty dashboard on Vercel**
- Confirm `POSTGRES_URL` is set.
- Run the tracker with the same `POSTGRES_URL`.
- Call `POST /api/sync` to populate `wallet_dashboard_stats`.

**CORS errors**
- Set `CORS_ORIGIN` to your exact Vercel deployment URL.

**Tracker Postgres sync fails**
- Install `psycopg2-binary`: `pip install psycopg2-binary`
- Verify the tracker can reach the Postgres host (use `POSTGRES_URL_NON_POOLING` if needed).

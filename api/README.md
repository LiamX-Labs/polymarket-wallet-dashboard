# Vercel API entry (disabled)

This folder contains the Vercel serverless entry point. Deployment is **disabled** by default.

To re-enable:
1. Rename `vercel.json.disabled` → `vercel.json` at the repo root
2. Set `VERCEL_ENABLED=true` in Vercel project settings (optional; `VERCEL=1` is auto-set on deploy)
3. Add Vercel Postgres / Neon and set `POSTGRES_URL`

Primary deployment target is **Render** — see `render.yaml` and `QUICKSTART-RENDER.md`.

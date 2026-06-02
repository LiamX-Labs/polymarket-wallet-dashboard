# Architecture Map: Polymarket Wallet Dashboard

## 1. High-Level Overview
A real-time dashboard for tracking Polymarket wallet performance. The system decouples high-frequency data collection (Python) from web-based visualization (TypeScript/React), using a synchronized database architecture to ensure performance and data integrity.

## 2. Component Breakdown
- **`tracker/` (Python)**: The data collection engine. It polls Polymarket APIs (CLOB/Gamma), analyzes wallet behavior, and stores raw data in `tracker.sqlite3`.
- **`bot/` (Python)**: Utility modules used by the tracker for analysis, reporting, and formatting.
- **`server/` (Node.js/TypeScript)**: The backend API. It runs a synchronization service to read from `tracker.sqlite3`, process/aggregate the data, and write it to `dashboard.db`. It also exposes REST endpoints for the frontend.
- **`client/` (React/TypeScript)**: The web UI. It fetches processed data from the API to visualize wallet metrics (today's performance, 7-day track record).

## 3. Data Flow/Pipeline
1. **Fetch**: `tracker/` fetches data from Polymarket APIs.
2. **Store (Raw)**: `tracker/` writes raw data to `tracker.sqlite3`.
3. **Sync**: `server/` (Sync Service) reads from `tracker.sqlite3` (read-only) every 5 minutes.
4. **Process/Aggregate**: `server/` calculates 7-day performance metrics.
5. **Store (Processed)**: `server/` writes aggregated data to `dashboard.db`.
6. **Serve**: `server/` (Express) serves processed data via REST API.
7. **Display**: `client/` (React) fetches and renders the dashboard UI.

## 4. Technology Stack
- **Data Collection**: Python 3.8+, `aiohttp`, `requests`.
- **Backend API**: Node.js, Express, TypeScript, `better-sqlite3`.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS.

## 5. Key Dependencies/Integrations
- Polymarket API (CLOB/Gamma).
- SQLite (for both tracker and dashboard databases).

## 6. Tracker/Server Interaction
The Python tracker and TypeScript server interact via a file-based bridge:
- The server opens the `tracker.sqlite3` file in **read-only mode**.
- The server's `sync.ts` script performs SQL queries against the tracker database to extract and aggregate necessary information, then updates the `dashboard.db` accordingly.

## 7. File Structure
```text
/home/william/polymarket-wallet-dashboard/
├───bot/
│   ├───analysis.py
│   ├───charts.py
│   ├───config.py
│   ├───formatters.py
├───client/
│   ├───src/
│   │   ├───App.tsx
│   │   ├───components/
│   │   ├───hooks/
│   ├───tsconfig.json
│   ├───vite.config.ts
├───server/
│   ├───src/
│   │   ├───db.ts
│   │   ├───index.ts
│   │   ├───sync.ts
│   │   ├───routes/
├───tracker/
│   ├───clob_client.py
│   ├───daily_alpha_report.py
│   ├───gamma_client.py
│   ├───market_tracker.py
│   ├───models.py
│   ├───tracker_db.py
│   └───wallet_analyzer.py
└───ARCHITECTURE_MAP.md
```

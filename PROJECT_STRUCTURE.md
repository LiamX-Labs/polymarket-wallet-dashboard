# Project Structure

```
polymarket-wallet-dashboard/
├── README.md                    # Full documentation
├── QUICKSTART.md               # Quick start guide
├── PROJECT_STRUCTURE.md        # This file
├── .gitignore                  # Git ignore rules
├── setup.sh                    # Automated setup script
│
├── server/                     # Backend (Node.js + Express + TypeScript)
│   ├── package.json           # Server dependencies
│   ├── tsconfig.json          # TypeScript config
│   ├── .env.example           # Environment template
│   ├── .env                   # Environment variables (create this)
│   │
│   └── src/
│       ├── index.ts           # Main server entry point
│       ├── db.ts              # Dashboard database operations
│       ├── sync.ts            # Sync service (reads from tracker DB)
│       ├── types.ts           # TypeScript interfaces
│       │
│       └── routes/
│           └── wallets.ts     # Wallet API endpoints
│
└── client/                     # Frontend (React + TypeScript + Tailwind)
    ├── package.json           # Client dependencies
    ├── tsconfig.json          # TypeScript config
    ├── tsconfig.node.json     # TypeScript config for Vite
    ├── vite.config.ts         # Vite bundler config
    ├── tailwind.config.js     # Tailwind CSS config
    ├── postcss.config.js      # PostCSS config
    ├── index.html             # HTML entry point
    │
    └── src/
        ├── main.tsx           # React entry point
        ├── App.tsx            # Main app component
        ├── index.css          # Global styles
        ├── types.ts           # TypeScript interfaces
        │
        ├── hooks/
        │   └── useWallets.ts  # Custom hook for wallet data
        │
        └── components/
            ├── WalletCard.tsx      # Today section component
            ├── WalletAddress.tsx   # Clickable wallet address
            ├── TrackRecord.tsx     # Track record metrics
            └── SortFilter.tsx      # Sorting controls
```

## File Descriptions

### Root Files

- **README.md**: Complete documentation with architecture, API, setup, troubleshooting
- **QUICKSTART.md**: 5-minute setup guide for getting started quickly
- **setup.sh**: Automated installation script for dependencies
- **.gitignore**: Git ignore patterns for node_modules, .env, databases, etc.

### Server (Backend)

#### Configuration
- **package.json**: Dependencies (express, better-sqlite3, cors, typescript)
- **tsconfig.json**: TypeScript compiler settings for Node.js
- **.env**: Environment variables (TRACKER_DB_PATH, DASHBOARD_DB_PATH, PORT)

#### Source Files
- **index.ts**:
  - Express server setup
  - CORS middleware
  - Auto-sync scheduler (every 5 minutes)
  - Health check endpoint
  - Graceful shutdown handler

- **db.ts**:
  - DashboardDB class
  - SQLite database operations
  - Schema initialization
  - CRUD operations for wallet stats
  - Sorting and filtering logic

- **sync.ts**:
  - SyncService class
  - Reads from tracker database
  - Calculates 7-day metrics
  - Aggregates position data
  - Win/loss calculations

- **types.ts**:
  - WalletStats interface
  - SortOptions interface
  - FilterOptions interface

- **routes/wallets.ts**:
  - GET /api/wallets (with sorting)
  - GET /api/wallets/:address
  - Error handling

### Client (Frontend)

#### Configuration
- **package.json**: Dependencies (react, typescript, tailwindcss)
- **vite.config.ts**: Dev server settings, API proxy to backend
- **tailwind.config.js**: Custom color scheme, dark theme
- **tsconfig.json**: TypeScript settings for React

#### Source Files
- **main.tsx**: React DOM rendering, app initialization

- **App.tsx**:
  - Main application layout
  - Wallet list rendering
  - Mobile-first responsive design
  - Loading and error states

- **index.css**: Global styles, scrollbar customization

- **types.ts**: TypeScript interfaces matching backend

#### Hooks
- **useWallets.ts**:
  - Fetch wallet data from API
  - Auto-refresh every 5 minutes
  - Sorting state management
  - Loading and error handling

#### Components
- **WalletCard.tsx**:
  - "Today" section display
  - 24h profit indicator
  - Recent trade info
  - Next trade countdown
  - StakeBet button (placeholder)

- **WalletAddress.tsx**:
  - Shortened address display
  - Click to reveal full address
  - Copy to clipboard functionality
  - Visual feedback on copy

- **TrackRecord.tsx**:
  - 7-day performance metrics
  - Win rate, trade count
  - Average win/loss amounts
  - Best/worst trades
  - Profit factor

- **SortFilter.tsx**:
  - Sort dropdown (profit, win rate, etc.)
  - Order toggle (asc/desc)
  - Filter controls

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    market_tracker.py                         │
│                  (Original Tracker System)                   │
│                                                              │
│  Collects wallet data → Stores in tracker.db                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Reads every 5 minutes
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Sync Service (sync.ts)                    │
│                                                              │
│  • Queries tracker.db for last 7 days                       │
│  • Calculates performance metrics                           │
│  • Aggregates trade data                                    │
│  • Writes to dashboard.db                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Stores processed data
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard DB (dashboard.db)               │
│                                                              │
│  wallet_dashboard_stats table (one row per wallet)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ API queries
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Express API (index.ts)                    │
│                                                              │
│  GET /api/wallets        → Returns all wallets (sorted)     │
│  GET /api/wallets/:addr  → Returns single wallet            │
│  POST /api/sync          → Manual sync trigger              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ HTTP requests (auto-refresh: 5min)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    React App (App.tsx)                       │
│                                                              │
│  useWallets hook → Fetches data → Renders components        │
│  • WalletCard (Today section)                               │
│  • TrackRecord (7-day metrics)                              │
│  • SortFilter (controls)                                    │
└─────────────────────────────────────────────────────────────┘
```

## Key Technologies

### Backend
- **Node.js**: Runtime environment
- **Express**: Web framework
- **TypeScript**: Type safety
- **better-sqlite3**: Fast SQLite driver
- **cors**: Cross-origin requests

### Frontend
- **React 18**: UI library
- **TypeScript**: Type safety
- **Vite**: Build tool (fast dev server)
- **Tailwind CSS**: Utility-first styling
- **PostCSS**: CSS processing

## Development Workflow

1. **Start Backend**: `cd server && npm run dev`
   - Listens on port 3001
   - Auto-syncs every 5 minutes
   - Provides REST API

2. **Start Frontend**: `cd client && npm run dev`
   - Listens on port 3000
   - Proxies /api to backend
   - Hot-reloads on changes

3. **Make Changes**: Edit source files
   - TypeScript for type safety
   - Auto-reload in development
   - Build for production with npm run build

## Production Build

```bash
# Backend
cd server
npm run build      # Compiles TypeScript → dist/
npm start          # Runs compiled JavaScript

# Frontend
cd client
npm run build      # Bundles React → dist/
# Serve dist/ with any static server
```

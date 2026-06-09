-- PostgreSQL schema for Polymarket Wallet Dashboard (Vercel Postgres / Neon)
-- Run once after creating your Vercel Postgres database:
--   psql $POSTGRES_URL -f sql/postgres-schema.sql

-- Tracker source table (written by Python tracker when POSTGRES_URL is set)
CREATE TABLE IF NOT EXISTS wallet_dashboard_summary (
  wallet TEXT PRIMARY KEY,

  profit_24h DOUBLE PRECISION NOT NULL DEFAULT 0,
  recent_trade_market TEXT,
  recent_trade_side TEXT,
  recent_trade_timestamp BIGINT,
  recent_trade_pnl DOUBLE PRECISION,
  avg_time_between_positions INTEGER NOT NULL DEFAULT 0,
  last_position_timestamp BIGINT,

  win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
  total_trades INTEGER NOT NULL DEFAULT 0,
  avg_trades_per_day DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_hold_time_seconds INTEGER NOT NULL DEFAULT 0,

  total_profits DOUBLE PRECISION NOT NULL DEFAULT 0,
  total_losses DOUBLE PRECISION NOT NULL DEFAULT 0,
  profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0,
  num_wins INTEGER NOT NULL DEFAULT 0,
  num_losses INTEGER NOT NULL DEFAULT 0,
  avg_win DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_loss DOUBLE PRECISION NOT NULL DEFAULT 0,
  best_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  best_trade_time_ago BIGINT,
  worst_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  worst_trade_time_ago BIGINT,
  best_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  best_perf_count INTEGER NOT NULL DEFAULT 0,
  worst_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  worst_perf_count INTEGER NOT NULL DEFAULT 0,
  avg_trade_size DOUBLE PRECISION NOT NULL DEFAULT 0,

  last_updated BIGINT NOT NULL,
  scan_event_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_summary_last_updated ON wallet_dashboard_summary (last_updated DESC);
CREATE INDEX IF NOT EXISTS idx_summary_profit_24h ON wallet_dashboard_summary (profit_24h DESC);

-- Dashboard API table (read by the frontend via Express API)
CREATE TABLE IF NOT EXISTS wallet_dashboard_stats (
  wallet TEXT PRIMARY KEY,

  profit_24h DOUBLE PRECISION NOT NULL DEFAULT 0,
  recent_trade_market TEXT,
  recent_trade_side TEXT,
  recent_trade_timestamp BIGINT,
  recent_trade_pnl DOUBLE PRECISION,
  avg_time_between_positions INTEGER NOT NULL DEFAULT 0,
  last_position_timestamp BIGINT,

  win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
  total_trades INTEGER NOT NULL DEFAULT 0,
  avg_trades_per_day DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_hold_time_seconds INTEGER NOT NULL DEFAULT 0,
  avg_win DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_loss DOUBLE PRECISION NOT NULL DEFAULT 0,
  best_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  best_trade_time_ago BIGINT,
  worst_trade_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  worst_trade_time_ago BIGINT,
  best_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  best_perf_time_ago BIGINT,
  best_perf_count INTEGER NOT NULL DEFAULT 0,
  worst_perf_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
  worst_perf_time_ago BIGINT,
  worst_perf_count INTEGER NOT NULL DEFAULT 0,
  num_wins INTEGER NOT NULL DEFAULT 0,
  num_losses INTEGER NOT NULL DEFAULT 0,
  avg_trade_size DOUBLE PRECISION NOT NULL DEFAULT 0,
  profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0,

  last_updated BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stats_profit_24h ON wallet_dashboard_stats (profit_24h);
CREATE INDEX IF NOT EXISTS idx_stats_win_rate ON wallet_dashboard_stats (win_rate);
CREATE INDEX IF NOT EXISTS idx_stats_total_trades ON wallet_dashboard_stats (total_trades);
CREATE INDEX IF NOT EXISTS idx_stats_last_updated ON wallet_dashboard_stats (last_updated);
CREATE INDEX IF NOT EXISTS idx_stats_avg_trade_size ON wallet_dashboard_stats (avg_trade_size);

export interface WalletStats {
  wallet: string;

  // Today metrics (last 24 hours)
  profit_24h: number;
  recent_trade_market: string | null;
  recent_trade_side: string | null;
  recent_trade_timestamp: number | null;
  recent_trade_pnl: number | null;
  avg_time_between_positions: number;
  last_position_timestamp: number | null;

  // Track Record metrics (7-day window)
  win_rate: number;
  total_trades: number;
  avg_trades_per_day: number;
  avg_hold_time_seconds: number;
  avg_win: number;
  avg_loss: number;
  best_trade_amount: number;
  best_trade_time_ago: number | null;
  best_perf_amount: number;
  best_perf_time_ago: number | null;
  worst_perf_amount: number;
  worst_perf_time_ago: number | null;
  num_wins: number;
  num_losses: number;
  avg_trade_size: number;
  profit_factor: number;

  last_updated: number;
}

export type SortField = keyof WalletStats;
export type SortOrder = 'asc' | 'desc';

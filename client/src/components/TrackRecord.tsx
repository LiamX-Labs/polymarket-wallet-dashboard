import { WalletStats } from '../types';

interface TrackRecordProps {
  wallet: WalletStats;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercentage(value: number): string {
  // Value is already 0-100 from tracker DB
  return `${value.toFixed(0)}%`;
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function formatTimeAgo(timestamp: number | null): string {
  if (!timestamp) return '-';

  const now = Math.floor(Date.now() / 1000);
  const diff = now - timestamp;

  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function TrackRecord({ wallet }: TrackRecordProps) {
  return (
    <div className="flex gap-3 text-xs min-w-max px-3">
      {/* WR / # trades */}
      <div className="flex flex-col w-[70px]">
        <div className="font-bold text-center">{formatPercentage(wallet.win_rate)}</div>
        <div className="text-gray-400 text-[11px] text-center">{wallet.total_trades} trades</div>
      </div>

      {/* Trades Daily / hold time */}
      <div className="flex flex-col w-[70px]">
        <div className="font-semibold text-center">{wallet.avg_trades_per_day.toFixed(0)}/day</div>
        <div className="text-gray-400 text-[11px] text-center">{formatTime(wallet.avg_hold_time_seconds)}</div>
      </div>

      {/* Avg $ win */}
      <div className="flex flex-col w-[60px]">
        <div className="font-semibold text-accent-green text-center">{formatCurrency(wallet.avg_win)}</div>
      </div>

      {/* Avg $ loss */}
      <div className="flex flex-col w-[60px]">
        <div className="font-semibold text-accent-red text-center">{formatCurrency(wallet.avg_loss)}</div>
      </div>

      {/* Best Trade $ / time ago */}
      <div className="flex flex-col w-[70px]">
        <div className="font-semibold text-accent-green text-center">
          {formatCurrency(wallet.best_trade_amount)}
        </div>
        <div className="text-gray-400 text-[11px] text-center">{formatTimeAgo(wallet.best_trade_time_ago)}</div>
      </div>

      {/* Worst Perf $ / time ago */}
      <div className="flex flex-col w-[70px]">
        <div className="font-semibold text-accent-red text-center">
          {formatCurrency(wallet.worst_perf_amount)}
        </div>
        <div className="text-gray-400 text-[11px] text-center">{formatTimeAgo(wallet.worst_perf_time_ago)}</div>
      </div>

      {/* Best Perf $ / # wins */}
      <div className="flex flex-col w-[70px]">
        <div className="font-semibold text-accent-green text-center">
          {formatCurrency(wallet.best_perf_amount)}
        </div>
        <div className="text-gray-400 text-[11px] text-center">{wallet.num_wins} wins</div>
      </div>

      {/* Worst perf / # losses */}
      <div className="flex flex-col w-[70px]">
        <div className="font-semibold text-accent-red text-center">
          {formatCurrency(wallet.worst_perf_amount)}
        </div>
        <div className="text-gray-400 text-[11px] text-center">{wallet.num_losses}</div>
      </div>

      {/* Avg $ trade size */}
      <div className="flex flex-col w-[60px]">
        <div className="font-semibold text-center">{formatCurrency(wallet.avg_trade_size)}</div>
      </div>

      {/* Profit Factor */}
      <div className="flex flex-col w-[50px]">
        <div className="font-semibold text-center">
          {wallet.profit_factor > 0 ? wallet.profit_factor.toFixed(1) : '-'}
        </div>
      </div>
    </div>
  );
}

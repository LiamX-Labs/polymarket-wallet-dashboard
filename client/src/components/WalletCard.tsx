import { WalletStats } from '../types';
import { WalletAddress } from './WalletAddress';

interface WalletCardProps {
  wallet: WalletStats;
  badgeColor: string;
  badgeText: string;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
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

function getNextTradeIn(avgTime: number, lastTrade: number | null): string {
  if (!lastTrade || avgTime === 0) return '-';

  const now = Math.floor(Date.now() / 1000);
  const elapsed = now - lastTrade;
  const remaining = avgTime - elapsed;

  if (remaining <= 0) return 'Due';
  if (remaining < 60) return `${remaining}s`;
  if (remaining < 3600) return `${Math.floor(remaining / 60)}m`;
  return `${Math.floor(remaining / 3600)}h`;
}

export function WalletCard({ wallet, badgeColor, badgeText }: WalletCardProps) {
  const pnlColor = wallet.recent_trade_pnl
    ? wallet.recent_trade_pnl >= 0
      ? 'text-accent-green'
      : 'text-accent-red'
    : 'text-dark-text';

  const profitColor = wallet.profit_24h >= 0 ? 'text-accent-green' : 'text-accent-red';

  return (
    <div className="flex items-center gap-2.5 py-1">
      {/* Left: Badge and Wallet Address */}
      <div className="flex flex-col items-center gap-0.5">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
          style={{ backgroundColor: badgeColor }}
        >
          {badgeText}
        </div>
        <div className="text-[10px]">
          <WalletAddress address={wallet.wallet} />
        </div>
      </div>

      {/* Center: Profit, Trade Info, PnL - All in one column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 24h Profit */}
        <div className={`text-base font-bold leading-tight ${profitColor}`}>
          {formatCurrency(wallet.profit_24h)}
        </div>

        {/* Recent Trade Market and Side with PnL */}
        <div className="flex items-center gap-1.5 text-[10px] leading-tight">
          <span className="text-gray-400">
            {wallet.recent_trade_market ? (
              <>
                {wallet.recent_trade_market.split(' ').slice(0, 2).join(' ')} ({wallet.recent_trade_side?.toLowerCase()})
              </>
            ) : (
              'No trades'
            )}
          </span>
          <span className={`text-sm font-semibold ${pnlColor}`}>
            {wallet.recent_trade_pnl ? formatCurrency(wallet.recent_trade_pnl) : '$0.0'}
          </span>
        </div>

        {/* Time ago */}
        <div className="text-[10px] text-gray-500 leading-tight">
          {formatTimeAgo(wallet.recent_trade_timestamp)}
        </div>
      </div>

      {/* Right: Next Trade Time and Button */}
      <div className="flex flex-col items-end gap-1">
        <div className="text-xs font-medium text-gray-300">
          {getNextTradeIn(
            wallet.avg_time_between_positions,
            wallet.last_position_timestamp
          )}
        </div>
        <button className="px-2 py-0.5 text-[10px] bg-purple-900/30 hover:bg-purple-800/40 border border-purple-700/50 rounded transition-colors text-purple-200 whitespace-nowrap">
          StakeBet [ ]&gt;
        </button>
      </div>
    </div>
  );
}

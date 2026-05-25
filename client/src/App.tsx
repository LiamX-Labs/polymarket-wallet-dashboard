import { useWallets } from './hooks/useWallets';
import { WalletCard } from './components/WalletCard';
import { TrackRecord } from './components/TrackRecord';
import { SortFilter } from './components/SortFilter';

// Generate random colors for wallet badges
const BADGE_COLORS = ['#ef4444', '#3b82f6', '#10b981', '#a855f7', '#f59e0b', '#ec4899'];
const BADGE_LETTERS = ['XA', 'XC', 'XE', 'XF', 'XG', 'XH'];

function getBadgeProps(index: number): { color: string; text: string } {
  return {
    color: BADGE_COLORS[index % BADGE_COLORS.length],
    text: BADGE_LETTERS[index % BADGE_LETTERS.length],
  };
}

export default function App() {
  const { wallets, loading, error, sortBy, sortOrder, setSorting } = useWallets();

  if (loading && wallets.length === 0) {
    return (
      <div className="min-h-screen bg-dark-bg flex items-center justify-center">
        <div className="text-dark-text">Loading wallet data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-dark-bg flex items-center justify-center">
        <div className="text-accent-red">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark-bg text-dark-text">
      {/* Header */}
      <header className="bg-dark-panel border-b border-dark-border p-4 sticky top-0 z-10">
        <h1 className="text-xl font-bold">Polymarket Wallet Tracker</h1>
        <p className="text-xs text-gray-400 mt-1">
          Live tracking • {wallets.length} wallets • Auto-refresh every 5m
        </p>
      </header>

      {/* Sort/Filter Controls */}
      <SortFilter sortBy={sortBy} sortOrder={sortOrder} onSort={setSorting} />

      {/* Main Content Layout - Two Column Structure */}
      <div className="px-3 pt-3 pb-3 flex gap-3">
        {/* Section 1: Today/Wallet Info Column */}
        <div className="flex-shrink-0 w-[180px] sm:w-[240px] md:w-[340px]">
          {/* Section 1 Header */}
          <div className="bg-red-900/20 px-3 py-1 rounded-t border-t border-x border-dark-border sticky top-[73px] z-10">
            <div className="flex justify-between items-center">
              <div className="text-[10px] text-red-400 font-semibold">
                Profit 24h / Recent Trade
              </div>
              <div className="text-[10px] text-red-400 font-semibold">
                Next trade in
              </div>
            </div>
          </div>

          {/* Section 1 Content - Wallet Cards */}
          <div className="space-y-2">
            {wallets.map((wallet, index) => {
              const badge = getBadgeProps(index);
              return (
                <div key={wallet.wallet} className="bg-dark-panel border border-dark-border h-[76px] flex items-center">
                  <div className="p-2 w-full">
                    <WalletCard
                      wallet={wallet}
                      badgeColor={badge.color}
                      badgeText={badge.text}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 2: Track Record Column (Unified Scroll) */}
        <div className="flex-1 min-w-0 overflow-x-auto">
          <div className="min-w-max">
            {/* Section 2 Header */}
            <div className="bg-red-900/20 rounded-t border-t border-x border-dark-border">
              <div className="px-3 py-1 flex gap-3 text-[9px] text-red-400 font-semibold">
                <div className="w-[70px] text-center">WR/k # trades</div>
                <div className="w-[70px] text-center">Trades Daily/ hold time</div>
                <div className="w-[60px] text-center">Avg $ win</div>
                <div className="w-[60px] text-center">Avg $ loss</div>
                <div className="w-[70px] text-center">Best Trade $/ time ago</div>
                <div className="w-[70px] text-center">Best Perf $/ time ago</div>
                <div className="w-[70px] text-center">Worst perf/ # wins</div>
                <div className="w-[70px] text-center">Worst perf/ # losses</div>
                <div className="w-[60px] text-center">Avg $ trade size</div>
                <div className="w-[50px] text-center">Profit Factor</div>
              </div>
            </div>

            {/* Section 2 Content - Track Records */}
            <div className="space-y-2">
              {wallets.map((wallet) => (
                <div key={wallet.wallet} className="bg-dark-panel border border-dark-border h-[76px] flex items-center">
                  <div className="py-2 w-full">
                    <TrackRecord wallet={wallet} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {wallets.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-400">
          No wallet data available. Make sure the tracker is running and syncing data.
        </div>
      )}
    </div>
  );
}

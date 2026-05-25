import { SortField, SortOrder } from '../types';

interface SortFilterProps {
  sortBy: SortField;
  sortOrder: SortOrder;
  onSort: (field: SortField, order: SortOrder) => void;
}

export function SortFilter({ sortBy, sortOrder, onSort }: SortFilterProps) {
  const sortOptions: { label: string; field: SortField }[] = [
    { label: 'Last Updated', field: 'last_updated' },
    { label: 'Latest Trade', field: 'recent_trade_timestamp' },
    { label: '24h Profit', field: 'profit_24h' },
    { label: 'Win Rate', field: 'win_rate' },
    { label: 'Total Trades', field: 'total_trades' },
    { label: 'Profit Factor', field: 'profit_factor' },
    { label: 'Best Trade', field: 'best_trade_amount' },
  ];

  const toggleOrder = () => {
    onSort(sortBy, sortOrder === 'asc' ? 'desc' : 'asc');
  };

  return (
    <div className="flex items-center gap-3 p-4 bg-dark-panel border-b border-dark-border">
      <span className="text-sm text-gray-400">Sort by:</span>
      <select
        value={sortBy}
        onChange={(e) => onSort(e.target.value as SortField, sortOrder)}
        className="bg-dark-border text-dark-text px-3 py-1 rounded text-sm border-none outline-none focus:ring-2 focus:ring-accent-blue"
      >
        {sortOptions.map((option) => (
          <option key={option.field} value={option.field}>
            {option.label}
          </option>
        ))}
      </select>

      <button
        onClick={toggleOrder}
        className="px-3 py-1 bg-dark-border hover:bg-accent-blue/20 rounded text-sm transition-colors"
      >
        {sortOrder === 'desc' ? '↓ Desc' : '↑ Asc'}
      </button>
    </div>
  );
}

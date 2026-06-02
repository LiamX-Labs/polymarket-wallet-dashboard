import { SortField, SortOrder } from '../types';
import { useState } from 'react';

interface SortFilterProps {
  sortBy: SortField;
  sortOrder: SortOrder;
  onSort: (field: SortField, order: SortOrder) => void;
  avgTradeSize?: { operator: string; value: number } | null;
  onAvgTradeSizeFilter?: (filter: { operator: string; value: number } | null) => void;
}

export function SortFilter({ sortBy, sortOrder, onSort, avgTradeSize, onAvgTradeSizeFilter }: SortFilterProps) {
  // PART 2 FIX: Initialize local state from the active filter (which defaults to <= $50)
  // This keeps the UI input fields in sync with the default filter on initial render
  const [filterValue, setFilterValue] = useState(avgTradeSize?.value?.toString() || '50');
  const [filterOperator, setFilterOperator] = useState(avgTradeSize?.operator || '<=');

  const sortOptions: { label: string; field: SortField }[] = [
    { label: 'Last Updated', field: 'last_updated' },
    { label: 'Latest Trade', field: 'recent_trade_timestamp' },
    { label: '24h Profit', field: 'profit_24h' },
    { label: 'Win Rate', field: 'win_rate' },
    { label: 'Total Trades', field: 'total_trades' },
    { label: 'Profit Factor', field: 'profit_factor' },
    { label: 'Best Trade', field: 'best_trade_amount' },
    { label: 'Avg Trade Size', field: 'avg_trade_size' },
  ];

  const toggleOrder = () => {
    onSort(sortBy, sortOrder === 'asc' ? 'desc' : 'asc');
  };

  const handleApplyFilter = () => {
    if (filterValue && onAvgTradeSizeFilter) {
      onAvgTradeSizeFilter({
        operator: filterOperator,
        value: parseFloat(filterValue),
      });
    }
  };

  const handleClearFilter = () => {
    setFilterValue('');
    if (onAvgTradeSizeFilter) {
      onAvgTradeSizeFilter(null);
    }
  };

  return (
    <div className="flex items-center gap-3 p-4 bg-dark-panel border-b border-dark-border flex-wrap">
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

      {/* Average Trade Size Filter */}
      <div className="flex items-center gap-2 ml-auto">
        <span className="text-sm text-gray-400">Filter by Avg Trade Size:</span>
        <select
          value={filterOperator}
          onChange={(e) => setFilterOperator(e.target.value)}
          className="bg-dark-border text-dark-text px-2 py-1 rounded text-sm border-none outline-none focus:ring-2 focus:ring-accent-blue"
        >
          <option value="<=">&lt;=</option>
          <option value=">=">&gt;=</option>
          <option value="<">&lt;</option>
          <option value=">">&gt;</option>
          <option value="=">=</option>
        </select>
        <input
          type="number"
          value={filterValue}
          onChange={(e) => setFilterValue(e.target.value)}
          placeholder="Enter amount"
          className="bg-dark-border text-dark-text px-3 py-1 rounded text-sm border-none outline-none focus:ring-2 focus:ring-accent-blue w-[120px]"
        />
        <button
          onClick={handleApplyFilter}
          className="px-3 py-1 bg-accent-blue hover:bg-accent-blue/80 rounded text-sm transition-colors"
        >
          Apply
        </button>
        {/* Show Clear whenever there's an active filter (including the default) */}
        {avgTradeSize && (
          <button
            onClick={handleClearFilter}
            className="px-3 py-1 bg-dark-border hover:bg-accent-red/20 rounded text-sm transition-colors"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { WalletStats, SortField, SortOrder } from '../types';

interface UseWalletsResult {
  wallets: WalletStats[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
  sortBy: SortField;
  sortOrder: SortOrder;
  setSorting: (field: SortField, order: SortOrder) => void;
  avgTradeSize: { operator: string; value: number } | null;
  setAvgTradeSizeFilter: (filter: { operator: string; value: number } | null) => void;
}

export function useWallets(): UseWalletsResult {
  const [wallets, setWallets] = useState<WalletStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortField>('last_updated');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [avgTradeSize, setAvgTradeSize] = useState<{ operator: string; value: number } | null>(null);

  const fetchWallets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      let apiUrl = import.meta.env.VITE_API_URL || '';
      if (apiUrl && !apiUrl.startsWith('http')) {
        apiUrl = `https://${apiUrl}`;
      }

      let url = `${apiUrl}/api/wallets?sort=${sortBy}&order=${sortOrder}`;
      
      if (avgTradeSize) {
        url += `&avgTradeSizeOp=${avgTradeSize.operator}&avgTradeSize=${avgTradeSize.value}`;
      }

      console.log('[useWallets] Environment:', {
        VITE_API_URL: import.meta.env.VITE_API_URL,
        apiUrl,
        fetchUrl: url
      });

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Failed to fetch wallets: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      setWallets(data.data || []);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      console.error('Error fetching wallets:', err);
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortOrder, avgTradeSize]);

  useEffect(() => {
    fetchWallets();
  }, [fetchWallets]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      fetchWallets();
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [fetchWallets]);

  const setSorting = useCallback((field: SortField, order: SortOrder) => {
    setSortBy(field);
    setSortOrder(order);
  }, []);

  const setAvgTradeSizeFilter = useCallback((filter: { operator: string; value: number } | null) => {
    setAvgTradeSize(filter);
  }, []);

  return {
    wallets,
    loading,
    error,
    refetch: fetchWallets,
    sortBy,
    sortOrder,
    setSorting,
    avgTradeSize,
    setAvgTradeSizeFilter,
  };
}

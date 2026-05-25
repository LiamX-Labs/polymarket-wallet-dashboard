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
}

export function useWallets(): UseWalletsResult {
  const [wallets, setWallets] = useState<WalletStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortField>('profit_24h');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const fetchWallets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const apiUrl = import.meta.env.VITE_API_URL || '';
      const response = await fetch(
        `${apiUrl}/api/wallets?sort=${sortBy}&order=${sortOrder}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch wallets');
      }

      const data = await response.json();
      setWallets(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error fetching wallets:', err);
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortOrder]);

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

  return {
    wallets,
    loading,
    error,
    refetch: fetchWallets,
    sortBy,
    sortOrder,
    setSorting,
  };
}

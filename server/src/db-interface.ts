import { WalletStats } from './types';

export interface DashboardDatabase {
  upsertWalletStats(stats: WalletStats): Promise<void>;
  getAllWallets(sortBy?: string, order?: 'asc' | 'desc'): Promise<WalletStats[]>;
  getWalletCount(): Promise<number>;
  getWalletByAddress(wallet: string): Promise<WalletStats | undefined>;
  close(): Promise<void>;
}

export interface SyncServiceLike {
  getLatestTrackerUpdate(): Promise<number>;
  needsSync(): Promise<boolean>;
  sync(): Promise<void>;
  close(): Promise<void>;
}

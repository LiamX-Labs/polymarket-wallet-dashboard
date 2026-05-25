import { Router, Request, Response } from 'express';
import { DashboardDB } from '../db';

export function createWalletsRouter(db: DashboardDB): Router {
  const router = Router();

  /**
   * GET /api/wallets
   * Get all wallets with optional sorting
   */
  router.get('/', (req: Request, res: Response) => {
    try {
      const sortBy = (req.query.sort as string) || 'profit_24h';
      const order = (req.query.order as 'asc' | 'desc') || 'desc';

      console.log(`[WALLETS API] Fetching wallets with sort=${sortBy}, order=${order}`);
      const wallets = db.getAllWallets(sortBy, order);
      console.log(`[WALLETS API] Found ${wallets.length} wallets in dashboard database`);

      res.json({
        success: true,
        count: wallets.length,
        data: wallets,
      });
    } catch (error) {
      console.error('[WALLETS API] Error fetching wallets:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to fetch wallets',
      });
    }
  });

  /**
   * GET /api/wallets/:address
   * Get specific wallet by address
   */
  router.get('/:address', (req: Request, res: Response) => {
    try {
      const wallet = db.getWalletByAddress(req.params.address);

      if (!wallet) {
        return res.status(404).json({
          success: false,
          error: 'Wallet not found',
        });
      }

      res.json({
        success: true,
        data: wallet,
      });
    } catch (error) {
      console.error('Error fetching wallet:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to fetch wallet',
      });
    }
  });

  return router;
}

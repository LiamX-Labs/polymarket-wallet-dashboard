import { Router, Request, Response } from 'express';
import { DashboardDB } from '../db';

export function createWalletsRouter(db: DashboardDB): Router {
  const router = Router();

  /**
   * GET /api/wallets
   * Get all wallets with optional sorting and filtering
   */
  router.get('/', (req: Request, res: Response) => {
    try {
      const sortBy = (req.query.sort as string) || 'profit_24h';
      const order = (req.query.order as 'asc' | 'desc') || 'desc';
      const avgTradeSizeOp = (req.query.avgTradeSizeOp as string) || null;
      const avgTradeSize = req.query.avgTradeSize ? parseFloat(req.query.avgTradeSize as string) : null;

      console.log(`[WALLETS API] Fetching wallets with sort=${sortBy}, order=${order}, avgTradeSizeFilter=${avgTradeSizeOp}${avgTradeSize ? ` ${avgTradeSize}` : ''}`);
      let wallets = db.getAllWallets(sortBy, order);
      
      // Apply average trade size filter if provided
      if (avgTradeSizeOp && avgTradeSize !== null) {
        wallets = wallets.filter(wallet => {
          switch (avgTradeSizeOp) {
            case '<=':
              return wallet.avg_trade_size <= avgTradeSize;
            case '>=':
              return wallet.avg_trade_size >= avgTradeSize;
            case '<':
              return wallet.avg_trade_size < avgTradeSize;
            case '>':
              return wallet.avg_trade_size > avgTradeSize;
            case '=':
              return wallet.avg_trade_size === avgTradeSize;
            default:
              return true;
          }
        });
      }

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

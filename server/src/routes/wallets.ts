import { Router, Request, Response } from 'express';
import { DashboardDatabase } from '../db-interface';

export function createWalletsRouter(db: DashboardDatabase): Router {
  const router = Router();

  router.get('/', async (req: Request, res: Response) => {
    try {
      const sortBy = (req.query.sort as string) || 'profit_24h';
      const order = (req.query.order as 'asc' | 'desc') || 'desc';
      const avgTradeSizeOp = (req.query.avgTradeSizeOp as string) || null;
      const avgTradeSize = req.query.avgTradeSize ? parseFloat(req.query.avgTradeSize as string) : null;

      let wallets = await db.getAllWallets(sortBy, order);

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

  router.get('/:address', async (req: Request, res: Response) => {
    try {
      const wallet = await db.getWalletByAddress(req.params.address);

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

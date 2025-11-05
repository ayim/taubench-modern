import type { Request, Response } from 'express';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { ErrorResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';

export const createHealthCheck =
  ({ database, monitoring }: { database: DatabaseClient; monitoring: MonitoringContext }) =>
  async (_req: Request, res: Response) => {
    const result = await database.checkLiveness();
    if (!result.success) {
      monitoring.logger.error('Database liveness failed', {
        errorMessage: result.error.message,
        errorName: result.error.code,
      });

      return res.status(500).json({
        error: { code: 'internal_error', message: 'Liveness failed' },
      } satisfies ErrorResponse);
    }

    res.status(200).send('OK');
  };

export const createReadinessCheck = () => (_req: Request, res: Response) => res.send('OK');

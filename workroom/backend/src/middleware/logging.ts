import type { NextFunction, Request, Response } from 'express';
import type { MonitoringContext } from '../monitoring/index.js';

export const createRequestLogger =
  ({ monitoring }: { monitoring: MonitoringContext }) =>
  (req: Request, _res: Response, next: NextFunction) => {
    monitoring.logger.info('New request', {
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });

    next();
  };

import type { NextFunction, Request, Response } from 'express';
import type { MonitoringContext } from '../monitoring/index.js';

const STATIC_ASSET_EXTENSIONS = /\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|map)$/i;
const DYNAMIC_DEV_ASSET_EXTENSIONS = /\.(tsx|ts|mjs)$/i;

export const createRequestLogger =
  ({ monitoring }: { monitoring: MonitoringContext }) =>
  (req: Request, _res: Response, next: NextFunction) => {
    const [targetPath] = req.url.split('?');

    if (
      req.method !== 'HEAD' &&
      req.method !== 'OPTIONS' &&
      /^\/(healthz|ready)/.test(targetPath) === false &&
      STATIC_ASSET_EXTENSIONS.test(targetPath) === false &&
      DYNAMIC_DEV_ASSET_EXTENSIONS.test(targetPath) === false
    ) {
      monitoring.logger.info('New request', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });
    }

    next();
  };

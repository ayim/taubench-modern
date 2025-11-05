import type { ExpressNextFunction, ExpressRequest, ExpressResponse } from '../interfaces.js';

export const noCache = (_req: ExpressRequest, res: ExpressResponse, next: ExpressNextFunction) => {
  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');

  next();
};

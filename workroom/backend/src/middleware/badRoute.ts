import type { ExpressRequest, ExpressResponse } from '../interfaces.js';

export const badPlatform = (_req: ExpressRequest, res: ExpressResponse) => {
  res
    .status(501)
    .send('Not implemented: if you are hitting this endpoint, your SPAR deployment is most likely misconfigured');
};

import type { NextFunction, Request, Response } from 'express';

export const serverHeaders = (_req: Request, res: Response, next: NextFunction) => {
  res.setHeader('server', 'spar');

  next();
};

import type { NextFunction, Request, Response } from 'express';

export const poweredByHeaders = (_req: Request, res: Response, next: NextFunction) => {
  res.setHeader('x-powered-by', 'spar');

  next();
};

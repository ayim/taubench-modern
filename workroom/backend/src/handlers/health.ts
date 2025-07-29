import type { Request, Response } from 'express';

export const createHealthCheck = () => (_req: Request, res: Response) => res.send('OK');

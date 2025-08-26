import type { Request, Response } from 'express';
import type { Configuration, WorkroomMeta } from '../configuration.js';

export const createGetWorkroomMeta =
  ({ configuration }: { configuration: Configuration }) =>
  (_req: Request, res: Response) => {
    res.json(configuration.workroomMeta satisfies WorkroomMeta);
  };

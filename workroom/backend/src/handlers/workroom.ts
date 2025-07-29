import type { Request, Response } from 'express';

export const createGetWorkroomMeta = () => (_req: Request, res: Response) => {
  res.json({
    features: {
      documentIntelligence: {
        enabled: false,
        reason: 'Doc Intel not available in SPAR YET',
      },
      developerMode: {
        enabled: false,
        reason: 'Showing action logs not available in SPAR YET',
      },
      agentDetails: {
        enabled: true,
        reason: null,
      },
    },
  });
};

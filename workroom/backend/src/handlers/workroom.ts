import type { Request, Response } from 'express';
import type { Configuration } from '../configuration.js';

export const createGetWorkroomMeta =
  ({ configuration }: { configuration: Configuration }) =>
  (_req: Request, res: Response) => {
    res.json({
      features: {
        documentIntelligence: {
          enabled: false,
          reason: 'Doc Intel not available in SPAR YET',
        },
        developerMode: {
          enabled: configuration.legacyRoutingUrl !== null,
          reason: configuration.legacyRoutingUrl ? 'Showing action logs not enabled in this environment' : null,
        },
        agentDetails: {
          enabled: true,
          reason: null,
        },
      },
    });
  };

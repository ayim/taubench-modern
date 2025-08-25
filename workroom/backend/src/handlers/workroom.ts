import type { Request, Response } from 'express';
import type { Configuration } from '../configuration.js';

export const createGetWorkroomMeta =
  ({ configuration }: { configuration: Configuration }) =>
  (_req: Request, res: Response) => {
    res.json({
      features: {
        documentIntelligence: {
          enabled: configuration.dataServer.mode !== 'disabled',
          reason: configuration.dataServer.mode === 'disabled' ? 'Doc Intel is disabled for this environment' : null,
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

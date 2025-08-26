import type { operations } from '@sema4ai/workroom-interface';
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
        mcpServersManagement: {
          enabled: true,
          reason: 'MCP servers are available in SPAR',
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
    } satisfies operations['getWorkroomMeta']['responses'][200]['content']['application/json']);
  };

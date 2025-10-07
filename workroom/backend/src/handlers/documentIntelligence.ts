import { createAgentSDK } from '@sema4ai/agent-server-interface';
import { z } from 'zod';
import type { Configuration } from '../configuration.js';
import { type ErrorResponse, type ExpressRequest, type ExpressResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';

const ConfigureDocumentIntelligenceInput = z.object({
  dataConnectionId: z.string().uuid(),
  integrations: z
    .array(
      z.object({
        type: z.literal('reducto'),
        endpoint: z.string(),
        api_key: z.string(),
      }),
    )
    .min(1)
    .max(1),
});

export const createConfigureDocumentIntelligence =
  ({ configuration, monitoring }: { configuration: Configuration; monitoring: MonitoringContext }) =>
  async (req: ExpressRequest, res: ExpressResponse): Promise<ExpressResponse> => {
    const bodyParseResult = ConfigureDocumentIntelligenceInput.safeParse(req.body);

    if (!bodyParseResult.success) {
      monitoring.logger.error('Failed to parse request body', {
        errorMessage: bodyParseResult.error.message,
      });
      return res.status(400).json({
        error: { code: 'invalid_request', message: `Failed to parse request body: ${bodyParseResult.error.message}` },
      } satisfies ErrorResponse);
    }

    const { integrations, dataConnectionId } = bodyParseResult.data;

    const agentSDK = createAgentSDK({
      baseUrl: configuration.agentServerInternalUrl,
      headers: {
        Authorization: 'Bearer TOKEN_NOT_REQUIRED',
      },
    });

    const agentServerResponse = await agentSDK.POST('/api/v2/document-intelligence', {
      body: {
        data_server: configuration.dataServerCredentials,
        integrations,
        data_connection_id: dataConnectionId,
      },
    });

    if (agentServerResponse.error) {
      monitoring.logger.error('Failed to configure Document Intelligence on Agent Server:', {
        errorMessage: agentServerResponse.error.error.message,
      });
      return res.status(500).json({
        error: { code: 'unexpected_error', message: 'Failed to configure Document Intelligence on Agent Server' },
      });
    }

    return res.status(200).json(null);
  };

import { randomUUID } from 'crypto';
import { createAgentSDK } from '@sema4ai/agent-server-interface';
import { z } from 'zod';
import type { Configuration } from '../configuration.js';
import { type ErrorResponse, type ExpressRequest, type ExpressResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { Result } from '../utils/result.js';

const AGENT_SERVER_DATA_SERVER_POSTGRES_CONNECTION_NAME = 'DocumentIntelligence';

type ConfigureDocumentIntelligenceInput = z.infer<typeof ConfigureDocumentIntelligenceInput>;
const ConfigureDocumentIntelligenceInput = z.object({
  postgresConnectionUrl: z.string().url(),
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

type PostgresConfiguration = {
  host: string;
  port: string;
  user: string;
  password: string;
  database: string;
  schema: string | null;
};

const parsePostgresConnectionUrl = (
  postgresConnectionUrl: string,
): Result<
  PostgresConfiguration,
  {
    code:
      | 'data_server_postgres_connection_url_not_a_valid_url'
      | 'data_server_postgres_connection_url_bad_protocol'
      | 'data_server_postgres_connection_url_no_credentials'
      | 'data_server_postgres_connection_url_no_database';
    message: string;
  }
> => {
  const parsedUrl = (() => {
    try {
      return new URL(postgresConnectionUrl);
    } catch {
      return null;
    }
  })();
  if (!parsedUrl) {
    return {
      success: false,
      error: {
        code: 'data_server_postgres_connection_url_not_a_valid_url',
        message: 'Failed to parse postgres connection string as a URL',
      },
    };
  }

  if (parsedUrl.protocol !== 'postgresql:') {
    return {
      success: false,
      error: {
        code: 'data_server_postgres_connection_url_bad_protocol',
        message: `Unexpected protocol in postgres connection URL: ${parsedUrl.protocol}`,
      },
    };
  }

  if (!parsedUrl.username || !parsedUrl.password) {
    return {
      success: false,
      error: {
        code: 'data_server_postgres_connection_url_no_credentials',
        message: 'Postgres connection URL contains no credentials (username, password)',
      },
    };
  }

  const database = parsedUrl.pathname.replace(/^\//, '');
  if (database.length < 1) {
    return {
      success: false,
      error: {
        code: 'data_server_postgres_connection_url_no_database',
        message: 'Postgres connection URL contains no database',
      },
    };
  }

  const schema = parsedUrl.searchParams.get('schema');

  return {
    success: true,
    data: {
      host: parsedUrl.hostname,
      port: parsedUrl.port || '5432',
      user: parsedUrl.username,
      password: parsedUrl.password,
      database,
      schema,
    },
  };
};

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

    const { integrations, postgresConnectionUrl } = bodyParseResult.data;

    const postgresConnectionUrlParseResult = parsePostgresConnectionUrl(postgresConnectionUrl);
    if (!postgresConnectionUrlParseResult.success) {
      monitoring.logger.error('Failed to parse postgres connection URL', {
        errorCause: postgresConnectionUrlParseResult.error.code,
      });
      return res.status(400).json({
        error: {
          code: 'invalid_request',
          message: `Failed to parse postgres connection URL: ${postgresConnectionUrlParseResult.error.code}`,
        },
      } satisfies ErrorResponse);
    }
    const postgresConfiguration = postgresConnectionUrlParseResult.data;

    const agentSDK = createAgentSDK({
      baseUrl: configuration.agentServerInternalUrl,
      headers: {
        Authorization: 'Bearer TOKEN_NOT_REQUIRED',
      },
    });

    const agentServerResponse = await agentSDK.POST('/api/v2/document-intelligence', {
      body: {
        data_server: configuration.dataServerCredentials,
        integrations, // todo update for external_id
        data_connections: [
          {
            external_id: randomUUID(),
            name: AGENT_SERVER_DATA_SERVER_POSTGRES_CONNECTION_NAME,
            engine: 'postgres',
            configuration: postgresConfiguration,
          },
        ],
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

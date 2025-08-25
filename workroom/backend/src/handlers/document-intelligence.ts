import { randomUUID } from 'crypto';
import { readFile } from 'fs/promises';
import { createAgentSDK } from '@sema4ai/agent-server-interface';
import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import { z } from 'zod';
import type { Configuration } from '../configuration.js';
import { type ExpressRequest, type ExpressResponse } from '../interfaces.js';
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

type DataServerConnectionDetails = {
  credentials: {
    username: string;
    password: string;
  };
  api: {
    http: {
      url: string;
      port: number;
    };
    mysql: {
      host: string;
      port: number;
    };
  };
};

type DataServerConfigurationJson = z.infer<typeof DataServerConfigurationJson>;
const DataServerConfigurationJson = z.object({
  // This is just the subset of configuration we're interested in, i.e. the Data Server credentials + service ports
  auth: z.object({
    username: z.string(),
    password: z.string(),
  }),
  api: z.object({
    http: z.object({
      port: z.coerce.number(),
    }),
    mysql: z.object({
      port: z.coerce.number(),
    }),
  }),
});

type PostgresConfiguration = {
  host: string;
  port: string;
  user: string;
  password: string;
  database: string;
  schema: string | null;
};

const retrieveDataServerConnectionDetails = async ({
  configuration,
  monitoring,
}: {
  configuration: Pick<Configuration, 'controlPlaneUrl' | 'dataServer'>;
  monitoring: MonitoringContext;
}): Promise<
  Result<
    DataServerConnectionDetails,
    {
      code:
        | 'data_server_config_path_not_defined'
        | 'data_server_config_not_found'
        | 'data_server_config_failed_to_parse_as_json'
        | 'data_server_config_failed_to_parse';
      message: string;
    }
  >
> => {
  switch (configuration.dataServer.mode) {
    case 'local': {
      return retrieveDataServerConnectionDetailsFromFilesystem({
        configuration: configuration.dataServer,
        monitoring,
      });
    }
    case 'cloud': {
      return retrieveDataServerConnectionDetailsFromAce();
    }
    case 'disabled': {
      throw new Error('Data Server is disabled');
    }
    default: {
      exhaustiveCheck(configuration.dataServer);
    }
  }
};

const retrieveDataServerConnectionDetailsFromFilesystem = async ({
  configuration,
  monitoring,
}: {
  configuration: Extract<Configuration['dataServer'], { mode: 'local' }>;
  monitoring: MonitoringContext;
}): Promise<
  Result<
    DataServerConnectionDetails,
    {
      code:
        | 'data_server_config_path_not_defined'
        | 'data_server_config_not_found'
        | 'data_server_config_failed_to_parse_as_json'
        | 'data_server_config_failed_to_parse';
      message: string;
    }
  >
> => {
  const dataServerConfigurationPath = configuration.configurationFilePath;
  if (!dataServerConfigurationPath) {
    return {
      success: false,
      error: {
        code: 'data_server_config_path_not_defined',
        message: 'Data Server configuration path not defined',
      },
    };
  }

  const dataServerConfigurationFileContents: string | null = await (async () => {
    try {
      return await readFile(dataServerConfigurationPath, {
        encoding: 'utf-8',
      });
    } catch {
      return null;
    }
  })();
  if (dataServerConfigurationFileContents === null) {
    return {
      success: false,
      error: {
        code: 'data_server_config_not_found',
        message: `Data Server configuration file (${dataServerConfigurationPath}) not found`,
      },
    };
  }

  const dataServerConfigurationJson: Record<string, unknown> | null = (() => {
    try {
      return JSON.parse(dataServerConfigurationFileContents);
    } catch {
      return null;
    }
  })();
  if (dataServerConfigurationJson === null) {
    return {
      success: false,
      error: {
        code: 'data_server_config_failed_to_parse_as_json',
        message: `Failed to parse Data Server configuration file (${dataServerConfigurationPath}) as JSON`,
      },
    };
  }

  const dataServerConfigurationParseResult = DataServerConfigurationJson.safeParse(dataServerConfigurationJson);
  if (!dataServerConfigurationParseResult.success) {
    monitoring.logger.error('Failed to parse Data Server configuration', {
      errorMessage: dataServerConfigurationParseResult.error.message,
    });
    return {
      success: false,
      error: {
        code: 'data_server_config_failed_to_parse',
        message: `Failed to parse Data Server configuration file (${dataServerConfigurationPath})`,
      },
    };
  }
  const dataServerConfiguration = dataServerConfigurationParseResult.data;

  return {
    success: true,
    data: {
      credentials: {
        username: dataServerConfiguration.auth.username,
        password: dataServerConfiguration.auth.password,
      },
      api: {
        http: {
          url: 'http://data-server',
          port: dataServerConfiguration.api.http.port,
        },
        mysql: {
          host: 'data-server',
          port: dataServerConfiguration.api.mysql.port,
        },
      },
    },
  };
};

const retrieveDataServerConnectionDetailsFromAce = () => {
  throw new Error('"SEMA4AI_WORKROOM_DATA_SERVER_MODE=cloud" not implemented yet');
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
  ({
    configuration,
    monitoring,
  }: {
    configuration: Pick<Configuration, 'agentServerInternalUrl' | 'controlPlaneUrl' | 'dataServer'>;
    monitoring: MonitoringContext;
  }) =>
  async (req: ExpressRequest, res: ExpressResponse): Promise<ExpressResponse> => {
    const bodyParseResult = ConfigureDocumentIntelligenceInput.safeParse(req.body);

    if (!bodyParseResult.success) {
      monitoring.logger.error('Failed to parse request body', {
        errorMessage: bodyParseResult.error.message,
      });
      return res.status(400).send(`Failed to parse request body: ${bodyParseResult.error.message}`);
    }

    const { integrations, postgresConnectionUrl } = bodyParseResult.data;

    const postgresConnectionUrlParseResult = parsePostgresConnectionUrl(postgresConnectionUrl);
    if (!postgresConnectionUrlParseResult.success) {
      monitoring.logger.error('Failed to parse postgres connection URL', {
        errorCause: postgresConnectionUrlParseResult.error.code,
      });
      return res
        .status(400)
        .send(`Failed to parse postgres connection URL: ${postgresConnectionUrlParseResult.error.code}`);
    }
    const postgresConfiguration = postgresConnectionUrlParseResult.data;

    const dataServerCredentials = await retrieveDataServerConnectionDetails({ configuration, monitoring });
    if (!dataServerCredentials.success) {
      monitoring.logger.error('Failed to get Data Server credentials', {
        errorCause: dataServerCredentials.error.code,
      });
      return res.status(500).send('Failed to get Data Server credentials');
    }

    const agentSDK = createAgentSDK({
      baseUrl: configuration.agentServerInternalUrl,
      headers: {
        Authorization: 'Bearer TOKEN_NOT_REQUIRED',
      },
    });

    const agentServerResponse = await agentSDK.POST('/api/v2/document-intelligence', {
      body: {
        data_server: dataServerCredentials.data,
        integrations,
        data_connections: [
          {
            id: randomUUID(),
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
      return res.status(500).send('Failed to configure Document Intelligence on Agent Server');
    }

    return res.status(200).send();
  };

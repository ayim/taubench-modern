import {
  exhaustiveCheck,
  parseEnvVariable,
  parseEnvVariableBoolean,
  parseEnvVariableInteger,
} from '@sema4ai/robocloud-shared-utils';
import type { operations } from '@sema4ai/workroom-interface';

export type WorkroomMeta = operations['getWorkroomMeta']['responses']['200']['content']['application/json'];

export interface Configuration {
  agentServerInternalUrl: string;
  allowInsecureRequests: boolean;
  auth: {
    tokenIssuer: string;
  } & (
    | {
        type: 'none';
      }
    | {
        jwtPrivateKeyB64: string;
        type: 'snowflake';
      }
    | {
        controlPlaneUrl: string;
        jwtPrivateKeyB64: string;
        tokenIssuers: Array<string>;
        type: 'sema4-oidc-sso';
      }
    | {
        clientId: string;
        clientSecret: string;
        intermediaryCallbackRedirectUrl: string | null;
        jwtPrivateKeyB64: string;
        oidcServer: string;
        type: 'oidc';
      }
  );
  dataServerCredentials: {
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
  files:
    | { mode: 'disabled' }
    | {
        awsRegion: string;
        awsRoleArn: string;
        s3BucketName: string;
        mode: 'aws';
      }
    | {
        clientId: string;
        containerName: string;
        mode: 'azure';
        storageAccountName: string;
      };
  frontendMode: 'disk' | 'middleware';
  legacyRoutingUrl: string | null;
  metaUrl: string | null;
  ports: {
    internal: number;
    public: number;
  };
  session: {
    cookieMaxAgeMs: number;
    secret: string;
  } | null;
  tenant: {
    tenantId: string;
    tenantName: string;
  };
  userIdentity: {
    cacheTTL: number;
  };
  workroomMeta: WorkroomMeta;
}

export const getConfiguration = (): Configuration => {
  const portPublic = parseEnvVariableInteger('SEMA4AI_WORKROOM_PORT');
  const portInternal = parseEnvVariableInteger('SEMA4AI_WORKROOM_PORT_INTERNAL');

  const nodeEnv = (() => {
    const env = parseEnvVariable('NODE_ENV');

    switch (env) {
      case 'development':
      case 'production':
        return env;

      default:
        throw new Error(`Unsupported node environment: ${env}`);
    }
  })();

  const agentServerInternalUrl = parseEnvVariable('SEMA4AI_WORKROOM_AGENT_SERVER_URL');

  const allowInsecureRequests = process.env.SEMA4AI_WORKROOM_ALLOW_INSECURE_REQUESTS
    ? parseEnvVariableBoolean('SEMA4AI_WORKROOM_ALLOW_INSECURE_REQUESTS')
    : false;

  const auth = ((): Configuration['auth'] => {
    const mode = parseEnvVariable('SEMA4AI_WORKROOM_AUTH_MODE') as Configuration['auth']['type'];
    const tokenIssuer = process.env.SEMA4AI_WORKROOM_AGENT_SERVER_TOKEN_ISSUER
      ? parseEnvVariable('SEMA4AI_WORKROOM_AGENT_SERVER_TOKEN_ISSUER')
      : 'spar';

    switch (mode) {
      case 'none':
        return { tokenIssuer, type: 'none' };
      case 'snowflake': {
        return {
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          tokenIssuer,
          type: 'snowflake',
        };
      }
      case 'sema4-oidc-sso':
        return {
          controlPlaneUrl: parseEnvVariable('SEMA4AI_WORKROOM_CONTROL_PLANE_URL'),
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          tokenIssuer,
          tokenIssuers: parseEnvVariable('SEMA4AI_WORKROOM_TOKEN_ISSUERS')
            .split(';')
            .filter((issuer) => issuer.trim() !== ''),
          type: 'sema4-oidc-sso',
        };
      case 'oidc': {
        const oidcServer = parseEnvVariable('SEMA4AI_WORKROOM_OIDC_SERVER');

        return {
          clientId: parseEnvVariable('SEMA4AI_WORKROOM_OIDC_CLIENT_ID'),
          clientSecret: parseEnvVariable('SEMA4AI_WORKROOM_OIDC_CLIENT_SECRET'),
          intermediaryCallbackRedirectUrl: process.env.SEMA4AI_WORKROOM_DEV_OIDC_INTERMEDIARY_REDIRECT_URL
            ? parseEnvVariable('SEMA4AI_WORKROOM_DEV_OIDC_INTERMEDIARY_REDIRECT_URL')
            : null,
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          oidcServer,
          tokenIssuer,
          type: 'oidc',
        };
      }

      default:
        exhaustiveCheck(mode);
    }
  })();

  const files = ((): Configuration['files'] => {
    const mode: Configuration['files']['mode'] = process.env.SEMA4AI_WORKROOM_FILES_MODE
      ? (parseEnvVariable('SEMA4AI_WORKROOM_FILES_MODE') as Configuration['files']['mode'])
      : 'disabled';

    switch (mode) {
      case 'aws':
        return {
          awsRegion: parseEnvVariable('SEMA4AI_WORKROOM_FILES_AWS_REGION'),
          awsRoleArn: parseEnvVariable('SEMA4AI_WORKROOM_FILES_AWS_ROLE_ARN'),
          s3BucketName: parseEnvVariable('SEMA4AI_WORKROOM_FILES_S3_BUCKET'),
          mode: 'aws',
        };

      case 'azure':
        return {
          clientId: parseEnvVariable('SEMA4AI_WORKROOM_FILES_AZURE_CLIENT_ID'),
          containerName: parseEnvVariable('SEMA4AI_WORKROOM_FILES_AZURE_CONTAINER'),
          mode: 'azure',
          storageAccountName: parseEnvVariable('SEMA4AI_WORKROOM_FILES_AZURE_STORAGE_ACCOUNT_NAME'),
        };

      case 'disabled':
        return { mode: 'disabled' };

      default:
        exhaustiveCheck(mode);
    }
  })();

  const metaUrl = process.env.SEMA4AI_WORKROOM_META_URL ? parseEnvVariable('SEMA4AI_WORKROOM_META_URL') : null;

  const session = ((): Configuration['session'] => {
    const authMode = parseEnvVariable('SEMA4AI_WORKROOM_AUTH_MODE') as Configuration['auth']['type'];

    switch (authMode) {
      case 'oidc':
        return {
          cookieMaxAgeMs: 24 * 60 * 60 * 1000, // 1 day
          secret: parseEnvVariable('SEMA4AI_WORKROOM_SESSION_SECRET'),
        };

      case 'none':
      case 'snowflake':
      case 'sema4-oidc-sso':
        return null;

      default:
        exhaustiveCheck(authMode);
    }
  })();

  const tenant = ((): Configuration['tenant'] => {
    const authMode = parseEnvVariable('SEMA4AI_WORKROOM_AUTH_MODE') as Configuration['auth']['type'];

    switch (authMode) {
      case 'snowflake': {
        // Passed-in automatically by Snowflake when the service is running
        const snowflakeAccountId = parseEnvVariable('SNOWFLAKE_ACCOUNT').toLowerCase();

        return {
          tenantId: snowflakeAccountId,
          tenantName: 'Sema4ai x Snowflake',
        };
      }

      case 'oidc':
      case 'none':
        return {
          tenantId: parseEnvVariable('SEMA4AI_WORKROOM_TENANT_ID'),
          tenantName: 'Team Edition',
        };

      case 'sema4-oidc-sso': {
        const tenantId = parseEnvVariable('SEMA4AI_WORKROOM_TENANT_ID');

        return {
          tenantId,
          tenantName: tenantId,
        };
      }

      default:
        exhaustiveCheck(authMode);
    }
  })();

  const legacyRoutingUrl = process.env.SEMA4AI_WORKROOM_AGENT_ROUTER_URL
    ? parseEnvVariable('SEMA4AI_WORKROOM_AGENT_ROUTER_URL')
    : null;

  const enableSparOnlyFeatures = process.env.SEMA4AI_ENABLE_SPAR_ONLY_FEATURES
    ? parseEnvVariableBoolean('SEMA4AI_ENABLE_SPAR_ONLY_FEATURES')
    : false;
  const sparOnlyFeature = enableSparOnlyFeatures
    ? { enabled: true, reason: null }
    : { enabled: false, reason: 'This feature is not available for this deployment' };

  const dataServerHost = process.env.SEMA4AI_WORKROOM_DATA_SERVER_HOST_OVERRIDE ?? 'http://localhost';

  return {
    agentServerInternalUrl,
    allowInsecureRequests,
    auth,
    dataServerCredentials: {
      // Default credentials when using SKIP_CONFIGURATION
      // https://github.com/Sema4AI/data/blob/master/docker/data-server/default_config.json
      credentials: {
        username: 'sema4ai',
        password: 'sema4ai',
      },
      api: {
        http: {
          url: dataServerHost,
          port: 47334,
        },
        mysql: {
          host: dataServerHost,
          port: 47335,
        },
      },
    },
    files,
    frontendMode: nodeEnv === 'development' ? 'middleware' : 'disk',
    legacyRoutingUrl,
    metaUrl,
    ports: {
      internal: portInternal,
      public: portPublic,
    },
    session,
    tenant,
    userIdentity: {
      cacheTTL: 30 * 1000, // 30 seconds
    },
    workroomMeta: {
      features: {
        mcpServersManagement: sparOnlyFeature,
        deploymentWizard: sparOnlyFeature,
        settings: sparOnlyFeature,
        agentEvals: sparOnlyFeature,
        documentIntelligence: sparOnlyFeature,
        developerMode: {
          enabled: true,
          reason: null,
        },
        agentDetails: {
          enabled: true,
          reason: null,
        },
      },
    },
  };
};

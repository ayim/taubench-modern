import {
  exhaustiveCheck,
  parseEnvVariable,
  parseEnvVariableBoolean,
  parseEnvVariableInteger,
} from '@sema4ai/shared-utils';
import type { operations } from '@sema4ai/workroom-interface';
import { LogSeverity } from './monitoring/index.js';
import { SESSION_COOKIES_NOT_ACTIVE } from './session/utils.js';

export type WorkroomMeta = operations['getWorkroomMeta']['responses']['200']['content']['application/json'];

export interface Configuration {
  agentServerInternalUrl: string;
  sparVersion: string;
  allowInsecureRequests: boolean;
  auth: {
    autoPromoteEmails: Array<string>;
    roleManagement: boolean;
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
        clientId: string;
        clientSecret: string;
        intermediaryCallbackRedirectUrl: string | null;
        jwtPrivateKeyB64: string;
        oidcServer: string;
        scopes: Array<string>;
        type: 'oidc';
      }
  );
  database: {
    agentServerSchema: string;
    host: string;
    migrations: {
      lockTable: string;
      recordsTable: string;
    };
    name: string;
    password: string;
    pool: {
      max: number;
    };
    port: number;
    schema: string;
    username: string;
  };
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
  eaiLinkUrl: string | null;
  featuresUrl: string | null;
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
  logLevel: LogSeverity;
  metaUrl: string | null;
  ports: {
    internal: number;
    public: number;
  };
  publicApi: {
    rateLimit: number;
    rateLimitWindowMs: number;
  };
  secretManagement: {
    secret: string;
  };
  session: {
    secret: string;
  } | null;
  sessionCookieMaxAgeMs: number;
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
    const autoPromoteEmails = process.env.SEMA4AI_WORKROOM_AUTH_AUTO_PROMOTE
      ? parseEnvVariable('SEMA4AI_WORKROOM_AUTH_AUTO_PROMOTE')
          .split(/[,;]/g)
          .map((email) => email.trim())
          .filter((email) => email.length > 0)
      : [];

    switch (mode) {
      case 'none':
        return { autoPromoteEmails, roleManagement: false, tokenIssuer, type: 'none' };
      case 'snowflake': {
        return {
          autoPromoteEmails,
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          roleManagement: true,
          tokenIssuer,
          type: 'snowflake',
        };
      }
      case 'oidc': {
        const oidcServer = parseEnvVariable('SEMA4AI_WORKROOM_OIDC_SERVER');

        // Standard, required scopes:
        //  offline_access  => Refresh tokens
        //  openid          => ID tokens
        //  profile         => User info, like name etc.
        //  email           => Email, profile picture etc.
        const scopes = process.env.SEMA4AI_WORKROOM_OIDC_SCOPES
          ? parseEnvVariable('SEMA4AI_WORKROOM_OIDC_SCOPES').split(/\s+/g)
          : ['offline_access', 'openid', 'email', 'profile'];

        return {
          autoPromoteEmails,
          clientId: parseEnvVariable('SEMA4AI_WORKROOM_OIDC_CLIENT_ID'),
          clientSecret: parseEnvVariable('SEMA4AI_WORKROOM_OIDC_CLIENT_SECRET'),
          intermediaryCallbackRedirectUrl: process.env.SEMA4AI_WORKROOM_DEV_OIDC_INTERMEDIARY_REDIRECT_URL
            ? parseEnvVariable('SEMA4AI_WORKROOM_DEV_OIDC_INTERMEDIARY_REDIRECT_URL')
            : null,
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          roleManagement: true,
          oidcServer,
          scopes,
          tokenIssuer,
          type: 'oidc',
        };
      }

      default:
        exhaustiveCheck(mode);
    }
  })();

  const database: Configuration['database'] = {
    agentServerSchema: 'v2',
    host: parseEnvVariable('POSTGRES_HOST'),
    migrations: {
      lockTable: 'spar_migration_lock',
      recordsTable: 'spar_migrations',
    },
    name: parseEnvVariable('POSTGRES_DB'),
    password: parseEnvVariable('POSTGRES_PASSWORD'),
    pool: {
      max: 10,
    },
    port: process.env.POSTGRES_PORT ? parseEnvVariableInteger('POSTGRES_PORT') : 5432,
    schema: 'spar_backend',
    username: parseEnvVariable('POSTGRES_USER'),
  };

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

  const eaiLinkUrl = process.env.SEMA4AI_WORKROOM_EAI_URL ? parseEnvVariable('SEMA4AI_WORKROOM_EAI_URL') : null;

  const logLevel = ((): LogSeverity => {
    if (process.env.SEMA4AI_WORKROOM_LOG_LEVEL) {
      return LogSeverity.parse(parseEnvVariable('SEMA4AI_WORKROOM_LOG_LEVEL'));
    }

    return 'INFO';
  })();

  const featuresUrl = process.env.SEMA4AI_WORKROOM_FEATURES_URL
    ? parseEnvVariable('SEMA4AI_WORKROOM_FEATURES_URL')
    : null;
  const metaUrl = process.env.SEMA4AI_WORKROOM_META_URL ? parseEnvVariable('SEMA4AI_WORKROOM_META_URL') : null;

  const session = ((): Configuration['session'] => {
    const authMode = parseEnvVariable('SEMA4AI_WORKROOM_AUTH_MODE') as Configuration['auth']['type'];

    switch (authMode) {
      case 'oidc':
        return {
          secret: parseEnvVariable('SEMA4AI_WORKROOM_SESSION_SECRET'),
        };

      case 'snowflake':
        return {
          secret: SESSION_COOKIES_NOT_ACTIVE,
        };

      case 'none':
        return null;

      default:
        exhaustiveCheck(authMode);
    }
  })();
  const sessionCookieMaxAgeMs = 24 * 60 * 60 * 1000; // 1 day

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

  const sparVersion = process.env.SPAR_VERSION ?? 'dev';

  return {
    agentServerInternalUrl,
    sparVersion,
    allowInsecureRequests,
    auth,
    database,
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
    eaiLinkUrl,
    featuresUrl,
    files,
    frontendMode: nodeEnv === 'development' ? 'middleware' : 'disk',
    legacyRoutingUrl,
    logLevel,
    metaUrl,
    ports: {
      internal: portInternal,
      public: portPublic,
    },
    publicApi: {
      rateLimit: process.env.SEMA4AI_WORKROOM_PUBLIC_API_RATE_LIMIT
        ? parseEnvVariableInteger('SEMA4AI_WORKROOM_PUBLIC_API_RATE_LIMIT')
        : 50,
      rateLimitWindowMs: process.env.SEMA4AI_WORKROOM_PUBLIC_API_RATE_LIMIT_WINDOW_MS
        ? parseEnvVariableInteger('SEMA4AI_WORKROOM_PUBLIC_API_RATE_LIMIT_WINDOW_MS')
        : 10 * 1000,
    },
    secretManagement: {
      // So as to avoid having n different secrets, we use the session provided one AND the fallback
      secret: session?.secret ?? SESSION_COOKIES_NOT_ACTIVE,
    },
    session,
    sessionCookieMaxAgeMs,
    tenant,
    userIdentity: {
      cacheTTL: 30 * 1000, // 30 seconds
    },
    workroomMeta: {
      features: {
        // For ACE the values are defined here: https://github.com/Sema4AI/ace/blob/86a89c91c3d6f3623992e7a952a2cccb26b5059f/applications/router-service/src/interface.ts#L205
        // SPAR & SPCS: defined here - anything that is SPAR Only will be disabled in SPCS
        agentAuthoring: sparOnlyFeature,
        agentConfiguration: sparOnlyFeature,
        agentDetails: {
          enabled: true,
          reason: null,
        },
        agentEvals: sparOnlyFeature,
        deploymentWizard: sparOnlyFeature,
        developerMode: {
          enabled: true,
          reason: null,
        },
        documentIntelligence: sparOnlyFeature,
        mcpServersManagement: sparOnlyFeature,
        publicAPI: sparOnlyFeature,
        semanticDataModels: sparOnlyFeature,
        settings: sparOnlyFeature,
        userManagement: sparOnlyFeature,
        workerAgents: sparOnlyFeature,
      },
    },
  };
};

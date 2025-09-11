import { exhaustiveCheck, parseEnvVariable, parseEnvVariableInteger } from '@sema4ai/robocloud-shared-utils';
import type { operations } from '@sema4ai/workroom-interface';

export type WorkroomMeta = operations['getWorkroomMeta']['responses']['200']['content']['application/json'];

export interface Configuration {
  agentServerInternalUrl: string;
  controlPlaneUrl: string | null;
  dataServer: { mode: 'disabled' } | { mode: 'cloud' } | { mode: 'local'; configurationFilePath: string };
  auth: {
    tokenIssuer: string;
  } & (
    | {
        type: 'none';
      }
    | {
        jwtPrivateKeyB64: string;
        type: 'google';
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
  );
  frontendMode: 'disk' | 'middleware';
  legacyRoutingUrl: string | null;
  metaUrl: string | null;
  port: number;
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
  const port = parseEnvVariableInteger('SEMA4AI_WORKROOM_PORT');

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
  const controlPlaneUrl: Configuration['controlPlaneUrl'] = process.env.SEMA4AI_WORKROOM_CONTROL_PLANE_URL
    ? parseEnvVariable('SEMA4AI_WORKROOM_CONTROL_PLANE_URL')
    : null;

  const dataServer = ((): Configuration['dataServer'] => {
    const dataServerConfigurationPath: string | null = process.env.SEMA4AI_WORKROOM_DATA_SERVER_CONFIGURATION_PATH
      ? parseEnvVariable('SEMA4AI_WORKROOM_DATA_SERVER_CONFIGURATION_PATH')
      : null;

    if (dataServerConfigurationPath) {
      return {
        mode: 'local',
        configurationFilePath: dataServerConfigurationPath,
      };
    }

    if (controlPlaneUrl) {
      return {
        mode: 'cloud',
      };
    }

    return {
      mode: 'disabled',
    };
  })();

  const auth = ((): Configuration['auth'] => {
    const mode = parseEnvVariable('SEMA4AI_WORKROOM_AUTH_MODE');
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
      case 'google': {
        return {
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          tokenIssuer,
          type: 'google',
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

      default:
        throw new Error(`Unsupported auth mode: ${mode}`);
    }
  })();

  const metaUrl = process.env.SEMA4AI_WORKROOM_META_URL ? parseEnvVariable('SEMA4AI_WORKROOM_META_URL') : null;

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

      case 'google':
      case 'none':
        return {
          tenantId: 'spar',
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

  const sparOnlyFeature =
    process.env.SEMA4AI_ENABLE_SPAR_ONLY_FEATURES === 'true'
      ? { enabled: true, reason: null }
      : { enabled: false, reason: 'This feature is not available for this deployment' };

  return {
    agentServerInternalUrl,
    controlPlaneUrl,
    auth,
    dataServer,
    frontendMode: nodeEnv === 'development' ? 'middleware' : 'disk',
    legacyRoutingUrl,
    metaUrl,
    port,
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
        documentIntelligence: {
          enabled: dataServer.mode !== 'disabled',
          reason: dataServer.mode === 'disabled' ? 'Doc Intel is disabled for this environment' : null,
        },
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

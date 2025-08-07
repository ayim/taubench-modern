import { exhaustiveCheck, parseEnvVariable, parseEnvVariableInteger } from '@sema4ai/robocloud-shared-utils';

export interface Configuration {
  auth:
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
      };
  deployment:
    | {
        agentServerInternalUrl: string;
        type: 'spar';
      }
    | {
        metaUrl: string;
        type: 'ace';
      };
  frontendMode: 'disk' | 'middleware';
  legacyRoutingUrl: string | null;
  tenant: {
    tenantId: string;
    tenantName: string;
    type: 'static';
  };
  port: number;
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

  const auth = ((): Configuration['auth'] => {
    const mode = parseEnvVariable('SEMA4AI_WORKROOM_AUTH_MODE');
    switch (mode) {
      case 'none':
        return { type: 'none' };
      case 'snowflake': {
        return {
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          type: 'snowflake',
        };
      }
      case 'google': {
        return {
          jwtPrivateKeyB64: parseEnvVariable('SEMA4AI_WORKROOM_JWT_PRIVATE_KEY_B64'),
          type: 'google',
        };
      }

      default:
        throw new Error(`Unsupported auth mode: ${mode}`);
    }
  })();

  const deployment = ((): Configuration['deployment'] => {
    const type = parseEnvVariable('SEMA4AI_WORKROOM_DEPLOYMENT_TYPE') as Configuration['deployment']['type'];
    switch (type) {
      case 'ace':
        return {
          metaUrl: parseEnvVariable('SEMA4AI_WORKROOM_META_URL'),
          type: 'ace',
        };
      case 'spar':
        return {
          agentServerInternalUrl: parseEnvVariable('SEMA4AI_WORKROOM_AGENT_SERVER_URL'),
          type: 'spar',
        };

      default:
        throw new Error(`Unsupported deployment type: ${type}`);
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
          type: 'static',
        };
      }
      case 'google':
      case 'none':
        return {
          tenantId: 'spar',
          tenantName: 'SPAR DEV',
          type: 'static',
        };

      default:
        exhaustiveCheck(authMode);
    }
  })();

  const legacyRoutingUrl = process.env.SEMA4AI_WORKROOM_AGENT_ROUTER_URL
    ? parseEnvVariable('SEMA4AI_WORKROOM_AGENT_ROUTER_URL')
    : null;

  return {
    auth,
    deployment,
    frontendMode: nodeEnv === 'development' ? 'middleware' : 'disk',
    legacyRoutingUrl,
    port,
    tenant,
  };
};

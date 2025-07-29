import { parseEnvVariable, parseEnvVariableInteger } from '@sema4ai/robocloud-shared-utils';

export interface Configuration {
  auth:
    | {
        type: 'none';
      }
    | {
        jwtPrivateKeyB64: string;
        type: 'google';
      };
  deployment:
    | {
        agentServerInternalUrl: string;
        type: 'spar';
      }
    | {
        agentRouterInternalUrl: string;
        metaUrl: string;
        type: 'spcs';
      }
    | {
        metaUrl: string;
        type: 'ace';
      };
  frontendMode: 'disk' | 'middleware';
  port: number;
}

export const getConfiguration = (): Configuration => {
  const port = parseEnvVariableInteger('PORT');

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
    const mode = parseEnvVariable('AUTH_MODE');
    switch (mode) {
      case 'none':
        return { type: mode };
      case 'google': {
        const agentServerJWTPrivateKeyB64 = parseEnvVariable('AGENT_SERVER_JWT_PRIVATE_KEY_B64');

        return {
          type: mode,
          jwtPrivateKeyB64: agentServerJWTPrivateKeyB64,
        };
      }

      default:
        throw new Error(`Unsupported auth mode: ${mode}`);
    }
  })();

  const deployment = ((): Configuration['deployment'] => {
    const type = parseEnvVariable('DEPLOYMENT_TYPE') as Configuration['deployment']['type'];
    switch (type) {
      case 'ace':
        return {
          metaUrl: parseEnvVariable('META_URL'),
          type: 'ace',
        };
      case 'spcs':
        return {
          agentRouterInternalUrl: parseEnvVariable('AGENT_ROUTER_URL'),
          metaUrl: parseEnvVariable('META_URL'),
          type: 'spcs',
        };
      case 'spar':
        return {
          agentServerInternalUrl: parseEnvVariable('AGENT_SERVER_URL'),
          type: 'spar',
        };

      default:
        throw new Error(`Unsupported deployment type: ${type}`);
    }
  })();

  return {
    auth,

    deployment,
    frontendMode: nodeEnv === 'development' ? 'middleware' : 'disk',

    port,
  };
};

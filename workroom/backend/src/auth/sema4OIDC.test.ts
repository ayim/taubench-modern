import { randomUUID } from 'node:crypto';
import getPort from 'get-port';
import { http, HttpResponse } from 'msw';
import { setupServer, SetupServerApi } from 'msw/node';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createGetACEUser, type GetACEUser } from './sema4OIDC.js';
import type { Configuration } from '../configuration.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { Result } from '../utils/result.js';

describe('createGetACEUser', () => {
  const getConfiguration = () =>
    ({
      auth: {
        controlPlaneUrl: '',
        type: 'sema4-oidc-sso',
      },
      userIdentity: {
        cacheTTL: 300,
      },
    }) as Configuration;

  const monitoring = {
    logger: {
      debug: () => {},
      info: () => {},
      error: () => {},
    },
  } as MonitoringContext;

  it('returns a method', () => {
    const result = createGetACEUser({
      configuration: getConfiguration(),
      monitoring,
    });

    expect(result.getACEUser).toBeTypeOf('function');
  });

  describe('returned function', () => {
    let mockServer: SetupServerApi | null = null;
    let getACEUser: GetACEUser;
    let configuration: Configuration;
    const userId: string = randomUUID();

    beforeEach(async () => {
      const targetPort = await getPort();
      const targetServerUrl = `http://127.0.0.1:${targetPort}`;

      const baseConfig = getConfiguration();
      configuration = {
        ...baseConfig,
        auth: {
          ...(baseConfig.auth as Extract<Configuration['auth'], { type: 'sema4-oidc-sso' }>),
          controlPlaneUrl: targetServerUrl,
        },
      };

      mockServer = setupServer(
        http.post(`${targetServerUrl}/users`, async ({ request }) => {
          const body = await request.json();

          expect(body).toEqual([{ type: 'email', value: 'test@sema4.ai' }]);

          return HttpResponse.json({
            userId,
          });
        }),
      );

      mockServer.listen({
        onUnhandledRequest: () => {
          // Squelch
        },
      });

      getACEUser = createGetACEUser({
        configuration,
        monitoring,
      }).getACEUser;
    });

    afterEach(async () => {
      if (mockServer) {
        mockServer.close();
        mockServer = null;
      }
    });

    it('returns correctly for ace user IDs', async () => {
      const result = await getACEUser({ type: 'aceUserId', value: userId });

      expect(result.success).toBe(true);

      const successResult = result as Extract<Result<{ userId: string }>, { success: true }>;
      expect(successResult.data.userId).toEqual(userId);
    });

    it('returns correctly for identities', async () => {
      const result = await getACEUser({
        type: 'identities',
        value: [
          {
            type: 'email',
            value: 'test@sema4.ai',
          },
        ],
      });

      expect(result.success).toBe(true);

      const successResult = result as Extract<Result<{ userId: string }>, { success: true }>;
      expect(successResult.data.userId).toEqual(userId);
    });
  });
});

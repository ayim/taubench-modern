import type { Result } from '@sema4ai/shared-utils';
import { describe, expect, it } from 'vitest';
import { getRouteBehaviour, type RouteBehaviour } from './routing.js';
import type { Configuration } from '../configuration.js';
import { parsePrivateApiRequest } from './parsers.js';
import type { SignAgentTokenErrorOutcome } from '../utils/signing.js';

describe('getRouteBehaviour', () => {
  const configuration = {
    auth: {
      jwtPrivateKeyB64:
        'LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JR0hBZ0VBTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEJHMHdhd0lCQVFRZ2Y1TmZyRGNHejhwclpwS2QKYzZxWWJvUzhROUdxTkhNR3k4Z0JwZWxhMkFtaFJBTkNBQVNpWWI2alNydTltLzhLbXlzVjBuUFlaKzluR1p4YQoyRVVFZmFPWnQ1OXlBT1lta1JGZnlKVTNUcGVUSnRhRWpyalRFQUkyYkhRK2daN3p1SDlpaStXMQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg==',
      tokenIssuer: 'spar',
      type: 'sema4-oidc-sso',
    },
  } as Configuration;

  const getRoute = () => {
    const route = parsePrivateApiRequest({
      method: 'get',
      path: '/api/v2/threads/',
    });
    if (!route) {
      throw new Error('No route for request');
    }
    return route;
  };

  it('returns correct components for allowed route', () => {
    const route = getRoute();

    const behaviour = getRouteBehaviour({
      configuration,
      route,
      tenantId: 'spar',
      userId: 'test@sema4.ai',
    });

    expect(behaviour).toHaveProperty('isAllowed', true);
    expect(behaviour).toHaveProperty('permissions');
  });

  it('allows for signing tokens', async () => {
    const route = getRoute();

    const behaviour = getRouteBehaviour({
      configuration,
      route,
      tenantId: 'spar',
      userId: 'test@sema4.ai',
    }) as Extract<RouteBehaviour, { isAllowed: true }>;

    const token = (await behaviour.signAgentToken()) as Extract<
      Result<string, SignAgentTokenErrorOutcome>,
      { success: true }
    >;
    expect(token.success).toBe(true);
    expect(token.data).toSatisfy((data) => data.length > 0);
  });
});

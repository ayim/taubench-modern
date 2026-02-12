import type { Result } from '@sema4ai/shared-utils';
import { describe, expect, it } from 'vitest';
import { parsePrivateApiRequest } from './parsers.js';
import { getRouteBehaviour, type RouteBehaviour } from './routing.js';
import type { SignAgentTokenErrorOutcome } from '../utils/signing.js';

describe('getRouteBehaviour', () => {
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

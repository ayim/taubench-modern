import { describe, expect, it } from 'vitest';
import { extractGoogleUserIdentity, GOOGLE_AUTH_HEADER, type GoogleUserIdentityResult } from './google.js';
import type { MonitoringContext } from '../../monitoring/index.js';

describe('extractGoogleUserIdentity', () => {
  const monitoring = {
    logger: {
      info: () => {},
      error: () => {},
    },
  } as MonitoringContext;

  it('returns successfully for valid headers', () => {
    const result = extractGoogleUserIdentity({
      headers: {
        [GOOGLE_AUTH_HEADER.toLowerCase()]: 'accounts.google.com:109000000000000000000',
      },
      monitoring,
    });

    expect(result).toHaveProperty('success', true);

    const successResult = result as Extract<GoogleUserIdentityResult, { success: true }>;
    expect(successResult.data.userId).toEqual('109000000000000000000');
  });

  it('returns unsuccessfully for missing headers', () => {
    const result = extractGoogleUserIdentity({
      headers: {},
      monitoring,
    });

    expect(result).toHaveProperty('success', false);

    const failureResult = result as Extract<GoogleUserIdentityResult, { success: false }>;
    expect(failureResult.error.code).toEqual('unauthorized');
  });
});

import { describe, expect, it } from 'vitest';
import { extractSnowflakeUserIdentity, SNOWFLAKE_AUTH_HEADER, type SnowflakeUserIdentityResult } from './snowflake.js';
import type { MonitoringContext } from '../../monitoring/index.js';

describe('extractSnowflakeUserIdentity', () => {
  const monitoring = {
    logger: {
      info: () => {},
      error: () => {},
    },
  } as MonitoringContext;

  it('returns successfully for valid headers', () => {
    const result = extractSnowflakeUserIdentity({
      headers: {
        [SNOWFLAKE_AUTH_HEADER.toLowerCase()]: 'test@sema4.ai',
      },
      monitoring,
    });

    expect(result).toHaveProperty('success', true);

    const successResult = result as Extract<SnowflakeUserIdentityResult, { success: true }>;
    expect(successResult.data.userId).toEqual('test@sema4.ai');
  });

  it('returns unsuccessfully for missing headers', () => {
    const result = extractSnowflakeUserIdentity({
      headers: {},
      monitoring,
    });

    expect(result).toHaveProperty('success', false);

    const failureResult = result as Extract<SnowflakeUserIdentityResult, { success: false }>;
    expect(failureResult.error.code).toEqual('unauthorized');
  });
});

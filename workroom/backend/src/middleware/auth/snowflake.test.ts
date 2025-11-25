import { randomUUID } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { extractSnowflakeUserIdentity, type SnowflakeUserIdentityResult } from './snowflake.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { ExtractSessionResult, SessionManager } from '../../session/sessionManager.js';
import { SNOWFLAKE_AUTH_HEADER } from '../../utils/snowflake.js';

describe('extractSnowflakeUserIdentity', () => {
  const userId = randomUUID();

  const monitoring = {
    logger: {
      debug: () => {},
      info: () => {},
      error: () => {},
    },
  } as MonitoringContext;

  const sessionManager = {
    extractSessionFromHeaders: async (headers: Record<string, string>): Promise<ExtractSessionResult> => {
      if (!headers[SNOWFLAKE_AUTH_HEADER]) {
        return {
          success: false,
          error: {
            code: 'no_session',
            message: 'No session',
          },
        };
      }

      return {
        success: true,
        data: {
          auth: {
            stage: 'authenticated',
            userId,
            userRole: 'admin',
          },
          authType: 'snowflake',
        },
      };
    },
  } as unknown as SessionManager;

  it('returns successfully for valid headers', async () => {
    const result = await extractSnowflakeUserIdentity({
      headers: {
        [SNOWFLAKE_AUTH_HEADER.toLowerCase()]: 'test@sema4.ai',
      },
      monitoring,
      sessionManager,
    });

    expect(result).toHaveProperty('success', true);

    const successResult = result as Extract<SnowflakeUserIdentityResult, { success: true }>;
    expect(successResult.data.userId).toEqual(userId);
    expect(successResult.data.userRole).toEqual('admin');
  });

  it('returns unsuccessfully for missing headers', async () => {
    const result = await extractSnowflakeUserIdentity({
      headers: {},
      monitoring,
      sessionManager,
    });

    expect(result).toHaveProperty('success', false);

    const failureResult = result as Extract<SnowflakeUserIdentityResult, { success: false }>;
    expect(failureResult.error.code).toEqual('unauthorized');
  });
});

import type { Result } from '@sema4ai/shared-utils';
import type { SessionManager } from './sessionManager.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { MonitoringContext } from '../monitoring/index.js';

export const SESSION_COOKIES_NOT_ACTIVE = '__SESSION_COOKIES_NOT_ACTIVE__';

export const destroySessionsForUser = async ({
  database,
  monitoring,
  sessionManager,
  userId,
}: {
  database: DatabaseClient;
  monitoring: MonitoringContext;
  sessionManager: SessionManager;
  userId: string;
}): Promise<Result<void>> => {
  monitoring.logger.info('Destroying sessions for target user', {
    userId,
  });

  // Find any database sessions that refer to this user
  const activeSessionsResult = await database.findActiveSessionsForUser({ userId });
  if (!activeSessionsResult.success) {
    monitoring.logger.error('Failed fetching active user sessions', {
      errorMessage: activeSessionsResult.error.message,
      errorName: activeSessionsResult.error.code,
      userId,
    });

    return {
      success: false,
      error: {
        code: 'user_sessions_lookup_failure',
        message: `Failed fetching user active sessions: ${userId}: ${activeSessionsResult.error.message}`,
      },
    };
  }

  for (const { sessionId } of activeSessionsResult.data) {
    const destroyResult = await sessionManager.destroySessionForId(sessionId);
    if (!destroyResult.success) {
      monitoring.logger.error('Failed destroying session in store', {
        errorMessage: destroyResult.error.message,
        errorName: destroyResult.error.code,
        sessionId,
        userId,
      });

      return {
        success: false,
        error: {
          code: 'session_destroy_failure',
          message: `Failed destroying session in store: ${destroyResult.error.message}`,
        },
      };
    }

    monitoring.logger.info('Destroyed user session', {
      sessionId,
      userId,
    });
  }

  monitoring.logger.info('Destroyed all active sessions', {
    userId,
  });

  return {
    success: true,
    data: undefined,
  };
};

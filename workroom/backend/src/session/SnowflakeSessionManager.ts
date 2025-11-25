import type { Cookie, SessionData, Store } from 'express-session';
import { Session } from './payload.js';
import type { ExtractSessionResult, SessionManager } from './sessionManager.js';
import type { ExpressRequest } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { formatZodError } from '../utils/error.js';
import { caseless } from '../utils/parse.js';
import { headersToObject } from '../utils/request.js';
import { asResult, type Result } from '../utils/result.js';
import { SNOWFLAKE_AUTH_HEADER } from '../utils/snowflake.js';
import { stringToUUID } from '../utils/uuid.js';

const UNIQUE_SESSION_HEADER_NAMES: Array<Lowercase<string>> = ['x-forwarded-for', 'user-agent'];

export class SnowflakeSessionManager implements SessionManager {
  private monitoring: MonitoringContext;

  public readonly store: Store;

  constructor({ monitoring, store }: { monitoring: MonitoringContext; store: Store }) {
    this.monitoring = monitoring;
    this.store = store;
  }

  async clearSessionForRequest(req: ExpressRequest): Promise<Result<void>> {
    const sessionIdResult = this.extractSessionIdFromHeaders(headersToObject(req.headers));
    if (!sessionIdResult.success) {
      return sessionIdResult;
    }

    const sessionId = sessionIdResult.data;
    if (!sessionId) {
      this.monitoring.logger.error('No session to clear: No ID found');

      return {
        success: false,
        error: {
          code: 'invalid_session',
          message: 'Could not clear session',
        },
      };
    }

    this.monitoring.logger.info('Clear session', {
      sessionId,
    });

    return this.destroySessionForId(sessionId);
  }

  async destroySessionForId(sessionId: string): Promise<Result<void>> {
    this.monitoring.logger.info('Destroy session', {
      sessionId,
    });

    return asResult(
      () =>
        new Promise((resolve, reject) => {
          this.store.destroy(sessionId, (err) => {
            if (err) {
              return reject(err instanceof Error ? err : new Error(`Failed destroying session: ${err}`));
            }

            resolve();
          });
        }),
    );
  }

  async extractSessionFromHeaders(headers: Headers | Record<string, string>): Promise<ExtractSessionResult> {
    const sessionIdResult = this.extractSessionIdFromHeaders(headersToObject(headers));
    if (!sessionIdResult.success) {
      return sessionIdResult;
    }

    const sessionDataResult = await asResult(
      () =>
        new Promise<SessionData | null>((resolve, reject) => {
          this.store.get(sessionIdResult.data, (err, data) => {
            if (err) {
              return reject(err);
            }

            resolve(data ?? null);
          });
        }),
    );
    if (!sessionDataResult.success) {
      this.monitoring.logger.error('Failed retrieving session data', {
        errorMessage: sessionDataResult.error.message,
        errorName: sessionDataResult.error.code,
        sessionId: sessionIdResult.data,
      });

      return {
        success: false,
        error: {
          code: 'invalid_session',
          message: 'Failed retrieving session data',
        },
      };
    }

    if (!sessionDataResult.data) {
      return {
        success: false,
        error: {
          code: 'no_session',
          message: 'No session found',
        },
      };
    }

    const sessionResult = Session.safeParse(sessionDataResult.data);
    if (!sessionResult.success) {
      this.monitoring.logger.error('Failed parsing session data', {
        errorMessage: formatZodError(sessionResult.error),
        sessionId: sessionIdResult.data,
      });

      return {
        success: false,
        error: {
          code: 'invalid_session',
          message: 'Failed retrieving session data',
        },
      };
    }

    return {
      success: true,
      data: sessionResult.data,
    };
  }

  async extractSessionFromRequest(req: ExpressRequest): Promise<ExtractSessionResult> {
    return this.extractSessionFromHeaders(headersToObject(req.headers));
  }

  async setSessionOnRequest(req: ExpressRequest, session: Session): Promise<Result<void>> {
    const sessionIdResult = this.extractSessionIdFromHeaders(headersToObject(req.headers));
    if (!sessionIdResult.success) {
      return sessionIdResult;
    }

    const sessionId = sessionIdResult.data;
    if (!sessionId) {
      this.monitoring.logger.error('No session to set: No ID found');

      return {
        success: false,
        error: {
          code: 'invalid_session',
          message: 'Could not update session',
        },
      };
    }

    if (session === null) {
      return this.destroySessionForId(sessionId);
    }

    const sessionData: SessionData = {
      cookie: {} as Cookie,
      ...session,
    };

    return await asResult(
      () =>
        new Promise<void>((resolve, reject) => {
          this.store.set(sessionId, sessionData, (err) => {
            if (err) {
              return reject(err);
            }

            resolve();
          });
        }),
    );
  }

  private extractSessionIdFromHeaders(
    headers: Record<string, string>,
  ): Result<string, { code: 'no_session'; message: string }> {
    const caselessHeaders = caseless(
      headers instanceof Headers ? Object.fromEntries(Object.entries(headers)) : headers,
    );

    const userIdentityHeaderValue = caselessHeaders[SNOWFLAKE_AUTH_HEADER] ?? '';
    if (!userIdentityHeaderValue) {
      return {
        success: false,
        error: {
          code: 'no_session',
          message: 'No Snowflake current user header found',
        },
      };
    }

    const sessionUniquenessHeaderValue = ((): string => {
      for (const headerName of UNIQUE_SESSION_HEADER_NAMES) {
        const value = caselessHeaders[headerName];
        if (value) return value;
      }

      return '';
    })();

    const uniqueValue = `${userIdentityHeaderValue}${sessionUniquenessHeaderValue}`;
    const uuid = stringToUUID(uniqueValue);

    return {
      success: true,
      data: uuid,
    };
  }
}

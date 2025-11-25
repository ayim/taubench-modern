import cookieSigning from 'cookie-signature';
import type { Store } from 'express-session';
import { type ExpressRequest } from '../interfaces.js';
import { Session, sessionsEqual } from './payload.js';
import type { ExtractSessionResult, SessionManager } from './sessionManager.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { formatZodError } from '../utils/error.js';
import { caseless, parseCookies } from '../utils/parse.js';
import { asResult, type Result } from '../utils/result.js';

const COOKIE_PREFIX = 's4spar.';

export class HTTPSessionManager implements SessionManager {
  protected monitoring: MonitoringContext;
  private secret: string;

  public readonly sessionCookieName: string;
  public readonly store: Store;

  constructor({
    monitoring,
    secret,
    store,
    tenantId,
  }: {
    monitoring: MonitoringContext;
    secret: string;
    store: Store;
    tenantId: string;
  }) {
    this.monitoring = monitoring;
    this.secret = secret;
    this.sessionCookieName = `${COOKIE_PREFIX}${tenantId}`.toLowerCase().replace(/[^a-z0-9._-]+/g, '_');
    this.store = store;
  }

  async clearSessionForRequest(req: ExpressRequest): Promise<Result<void>> {
    this.monitoring.logger.info('Clear session', {
      sessionId: req.session?.id,
    });

    return asResult(
      () =>
        new Promise<void>((resolve) => {
          if (req.session?.destroy) {
            req.session.destroy(() => resolve());
          } else {
            resolve();
          }
        }),
    );
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
    const cookies = parseCookies(
      (headers instanceof Headers ? headers.get('cookie') : caseless(headers)['cookie']) ?? '',
    );

    if (!cookies[this.sessionCookieName]) {
      return {
        success: false,
        error: {
          code: 'no_session',
          message: 'No session cookie found',
        },
      };
    }

    const sessionData = cookies[this.sessionCookieName].replace(/^s:/, '');
    const sessionId = cookieSigning.unsign(sessionData, this.secret);
    if (!sessionId) {
      this.monitoring.logger.error('No session found for session cookie');

      return {
        success: false,
        error: {
          code: 'no_session',
          message: 'No session found for provided cookie',
        },
      };
    }

    const sessionResult = await new Promise<ExtractSessionResult>((resolve) => {
      this.store.get(sessionId, (err, sess) => {
        if (err) {
          return resolve({
            success: false,
            error: {
              code: 'invalid_session',
              message: `Failed retrieving session from store: ${err}`,
            },
          });
        }

        if (!sess) {
          // Empty session
          return resolve({
            success: false,
            error: {
              code: 'no_session',
              message: 'No session found',
            },
          });
        }

        const output = Session.safeParse(sess);
        if (!output.success) {
          this.monitoring.logger.error('Failed extracting session from headers', {
            errorMessage: formatZodError(output.error),
          });

          return resolve({
            success: false,
            error: {
              code: 'invalid_session',
              message: 'Invalid session data',
            },
          });
        }

        resolve(output);
      });
    });

    return sessionResult;
  }

  async extractSessionFromRequest(req: ExpressRequest): Promise<ExtractSessionResult> {
    await new Promise<void>((resolve, reject) => {
      req.session.reload((err) => {
        if (err) {
          return reject(err);
        }

        resolve();
      });
    });

    const sessionResult = Session.safeParse(req.session);

    if (!sessionResult.success) {
      this.monitoring.logger.error('Failed extracting session from request', {
        errorMessage: formatZodError(sessionResult.error),
      });

      return {
        success: false,
        error: {
          code: 'invalid_session',
          message: 'Invalid session data',
        },
      };
    }

    return sessionResult;
  }

  async setSessionOnRequest(req: ExpressRequest, session: Session): Promise<Result<void>> {
    try {
      if (session === null) {
        // Iterate and drop keys from session - soft clear
        Object.keys(req.session).forEach((key) => {
          if (key !== 'id' && key !== 'cookie') {
            delete (req.session as unknown as Record<string, unknown>)[key];
          }
        });
      } else {
        Object.assign(req.session, session);
      }

      await new Promise<void>((resolve, reject) => {
        req.session.save((err) => {
          if (err) {
            return reject(err);
          }

          resolve();
        });
      });

      this.monitoring.logger.info('Session saved', {
        sessionId: req.session.id,
      });

      // Perform verification
      await new Promise<void>((resolve, reject) => {
        this.store.get(req.session.id, (err, retrieved) => {
          if (err) {
            return reject(err);
          }

          if (!retrieved) {
            return reject(new Error('Failed verifying saved session: Session data empty'));
          }

          const checkSession = retrieved as unknown as Session;
          if (!sessionsEqual(checkSession, session)) {
            return reject(new Error('Failed verifying saved session: Retrieved session did not match save target'));
          }

          resolve();
        });
      });

      return {
        success: true,
        data: undefined,
      };
    } catch (err) {
      this.monitoring.logger.error('Failed saving new session data', {
        error: err as Error,
      });

      return {
        success: false,
        error: {
          code: 'session_save_failure',
          message: 'Failed saving to session',
        },
      };
    }
  }
}

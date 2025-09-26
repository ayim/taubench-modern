import cookieSigning from 'cookie-signature';
import type { Store } from 'express-session';
import z from 'zod';
import { Tokens, type ExpressRequest } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { formatZodError } from '../utils/error.js';
import { caseless, parseCookies } from '../utils/parse.js';
import type { Result } from '../utils/result.js';

export type ExtractSessionResult = Result<
  Session,
  { code: 'invalid_session' | 'no_session' | 'session_empty'; message: string }
>;

export type Session = z.infer<typeof Session>;
const Session = z.object({
  auth: z
    .object({
      tokens: Tokens,
      type: z.literal('oidc'),
    })
    .optional(),
  codeVerifier: z.string().optional(),
});

const COOKIE_NAME = 's4spar';

export class SessionManager {
  protected monitoring: MonitoringContext;
  private secret: string;
  public readonly store: Store;

  constructor({ monitoring, secret, store }: { monitoring: MonitoringContext; secret: string; store: Store }) {
    this.monitoring = monitoring;
    this.secret = secret;
    this.store = store;
  }

  get sessionCookieName(): string {
    return COOKIE_NAME;
  }

  async clearSessionForRequest(req: ExpressRequest): Promise<void> {
    this.monitoring.logger.info('Clear session', {
      sessionId: req.session?.id,
    });

    return new Promise<void>((resolve) => {
      if (req.session?.destroy) {
        req.session.destroy(() => resolve());
      } else {
        resolve();
      }
    });
  }

  async extractSessionFromHeaders(headers: Headers | Record<string, string>): Promise<ExtractSessionResult> {
    const cookies = parseCookies(
      (headers instanceof Headers ? headers.get('cookie') : caseless(headers)['cookie']) ?? '',
    );

    if (!cookies[COOKIE_NAME]) {
      return {
        success: false,
        error: {
          code: 'no_session',
          message: 'No session cookie found',
        },
      };
    }

    const sessionData = cookies[COOKIE_NAME].replace(/^s:/, '');
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
          return resolve({
            success: false,
            error: {
              code: 'invalid_session',
              message: `Failed parsing session data: ${formatZodError(output.error)}`,
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

    const session = req.session as unknown as Session;
    if (!session) {
      return {
        success: false,
        error: {
          code: 'no_session',
          message: 'No session found',
        },
      };
    }

    if (!session.auth?.type && !session.codeVerifier) {
      return {
        success: false,
        error: {
          code: 'session_empty',
          message: 'Session present but empty',
        },
      };
    }

    const sessionResult = Session.safeParse(req.session);
    if (!sessionResult.success) {
      return {
        success: false,
        error: {
          code: 'invalid_session',
          message: `Failed extracting session from request: Session data invalid: ${formatZodError(sessionResult.error)}`,
        },
      };
    }

    return sessionResult;
  }

  async setSessionOnRequest(req: ExpressRequest, session: Session): Promise<Result<void>> {
    try {
      const reqSession = req.session as unknown as Session;
      reqSession.auth = session.auth;
      reqSession.codeVerifier = session.codeVerifier;

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

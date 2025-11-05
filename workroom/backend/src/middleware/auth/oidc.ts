import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { AuthManager } from '../../auth/AuthManager.js';
import { upsertOIDCUser } from '../../auth/utils/oidcUserRegistration.js';
import type { DatabaseClient } from '../../database/DatabaseClient.js';
import type { ErrorResponse, ExpressNextFunction, ExpressRequest, ExpressResponse } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { SessionManager } from '../../session/SessionManager.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

type OIDCUserIdentityResult = Result<
  {
    userId: string;
  },
  | {
      code: 'unauthorized';
      message: string;
    }
  | {
      code: 'forbidden';
      message: string;
    }
  | {
      code: 'expired';
      message: string;
    }
  | {
      code: 'pending';
      message: string;
    }
>;

export const handleOIDCAuthCheck = async ({
  authManager,
  database,
  monitoring,
  next,
  req,
  res,
  sessionManager,
}: {
  authManager: AuthManager;
  database: DatabaseClient;
  monitoring: MonitoringContext;
  next: ExpressNextFunction;
  req: ExpressRequest;
  res: ExpressResponse;
  sessionManager: SessionManager;
}) => {
  const userIdentityResult: OIDCUserIdentityResult = await extractOIDCUserIdentity({
    authManager,
    headers: extractHeadersFromRequest(req.headers),
    monitoring,
    sessionManager,
  });

  if (!userIdentityResult.success) {
    monitoring.logger.error('Failed to extract OIDC user identity', {
      errorName: userIdentityResult.error.code,
      errorMessage: userIdentityResult.error.message,
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });

    switch (userIdentityResult.error.code) {
      case 'unauthorized':
        await sessionManager.clearSessionForRequest(req);
        return res
          .status(401)
          .json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
      case 'forbidden':
        await sessionManager.clearSessionForRequest(req);
        return res.status(403).json({ error: { code: 'forbidden', message: 'Forbidden' } } satisfies ErrorResponse);
      case 'pending':
        return res.status(409).send('Conflict: Wait for auth');
      case 'expired': {
        monitoring.logger.info('OIDC access token expired');

        const refreshResult = await refreshOIDCToken({
          authManager,
          database,
          monitoring,
          req,
          sessionManager,
        });

        if (!refreshResult.success) {
          // Monitoring logs already emitted
          await sessionManager.clearSessionForRequest(req);

          return res
            .status(401)
            .json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
        }

        res.locals.authSub = refreshResult.data.userId;

        return next();
      }

      default:
        exhaustiveCheck(userIdentityResult.error);
    }
  }

  res.locals.authSub = userIdentityResult.data.userId;

  return next();
};

/**
 * Extract the internal user identity by reconciling with OIDC
 */
export const extractOIDCUserIdentity = async ({
  authManager,
  headers,
  monitoring,
  sessionManager,
}: {
  authManager: AuthManager;
  headers: Record<string, string>;
  monitoring: MonitoringContext;
  sessionManager: SessionManager;
}): Promise<OIDCUserIdentityResult> => {
  const sessionResult = await sessionManager.extractSessionFromHeaders(headers);
  if (!sessionResult.success) {
    switch (sessionResult.error.code) {
      case 'invalid_session':
        monitoring.logger.error('OIDC authentication attempted but an invalid session was provided', {
          errorName: sessionResult.error.code,
          errorMessage: sessionResult.error.message,
        });

        return {
          success: false,
          error: {
            code: 'forbidden',
            message: 'Session validation failed',
          },
        };
      case 'no_session':
        monitoring.logger.error('OIDC authentication attempted but no session was found', {
          errorName: sessionResult.error.code,
          errorMessage: sessionResult.error.message,
        });

        return {
          success: false,
          error: {
            code: 'unauthorized',
            message: 'No session',
          },
        };

      default:
        exhaustiveCheck(sessionResult.error.code);
    }
  }

  if (!sessionResult.data) {
    monitoring.logger.error('OIDC authentication attempted but an empty session was provided');

    return {
      success: false,
      error: {
        code: 'forbidden',
        message: 'Session validation failed due to incomplete login',
      },
    };
  }

  if (sessionResult.data.authType !== 'oidc') {
    monitoring.logger.error('OIDC authentication attempted but session authentication was not in OIDC mode', {
      errorMessage: `Bad auth type for session: ${sessionResult.data.authType}`,
    });

    return {
      success: false,
      error: {
        code: 'forbidden',
        message: 'Session validation failed due to an invalid session',
      },
    };
  }

  if (sessionResult.data.auth.stage !== 'authenticated') {
    monitoring.logger.error(
      'OIDC authentication attempted but an incomplete session was provided: Waiting for resolution',
    );

    return {
      success: false,
      error: {
        code: 'pending',
        message: 'Session validation failed due to a pending login',
      },
    };
  }

  const { tokens } = sessionResult.data.auth;

  // Validate token validity
  const validityResult = await authManager.validateTokens({ tokens });
  if (!validityResult.success) {
    return {
      success: false,
      error: {
        code: 'expired',
        message: `Tokens are invalid: ${validityResult.error.message}`,
      },
    };
  }

  return {
    success: true,
    data: {
      userId: sessionResult.data.auth.userId,
    },
  };
};

export const refreshOIDCToken = async ({
  authManager,
  database,
  monitoring,
  req,
  sessionManager,
}: {
  authManager: AuthManager;
  database: DatabaseClient;
  monitoring: MonitoringContext;
  req: ExpressRequest;
  sessionManager: SessionManager;
}): Promise<Result<{ userId: string }>> => {
  const sessionResult = await sessionManager.extractSessionFromRequest(req);

  if (!sessionResult.success) {
    monitoring.logger.error('Unable to handle expired tokens: Invalid session', {
      errorName: sessionResult.error.code,
      errorMessage: sessionResult.error.message,
    });

    await sessionManager.clearSessionForRequest(req);

    return {
      success: false,
      error: {
        code: 'invalid_session',
        message: `Invalid session: ${sessionResult.error.message}`,
      },
    };
  }

  if (!sessionResult.data) {
    monitoring.logger.error('Unable to handle expired tokens: No session data');

    const clearSessionResult = await sessionManager.clearSessionForRequest(req);
    if (!clearSessionResult.success) {
      monitoring.logger.error('Failed clearing session for expired tokens', {
        errorName: clearSessionResult.error.code,
        errorMessage: clearSessionResult.error.message,
      });
    }

    return {
      success: false,
      error: {
        code: 'invalid_session',
        message: 'Invalid session: No tokens found in session',
      },
    };
  }

  if (sessionResult.data.authType !== 'oidc' || sessionResult.data.auth.stage !== 'authenticated') {
    monitoring.logger.error('Unable to handle expired tokens: Session is in incorrect state for refreshing');

    const clearSessionResult = await sessionManager.clearSessionForRequest(req);
    if (!clearSessionResult.success) {
      monitoring.logger.error('Failed clearing session for invalid state', {
        errorName: clearSessionResult.error.code,
        errorMessage: clearSessionResult.error.message,
      });
    }

    return {
      success: false,
      error: {
        code: 'invalid_session',
        message: 'Invalid session',
      },
    };
  }

  const authPayload = sessionResult.data.auth;

  monitoring.logger.info('Refreshing user tokens');
  const userIdResult = await authManager.refreshSemaphore.use(authPayload.tokens.refreshToken ?? '-', async () => {
    const refreshResult = await authManager.refreshTokens({ tokens: authPayload.tokens });
    if (!refreshResult.success) {
      monitoring.logger.error('Unable to handle expired tokens: Token refresh failed', {
        errorName: refreshResult.error.code,
        errorMessage: refreshResult.error.message,
      });

      const clearSessionResult = await sessionManager.clearSessionForRequest(req);
      if (!clearSessionResult.success) {
        monitoring.logger.error('Failed clearing session for failed refresh', {
          errorName: clearSessionResult.error.code,
          errorMessage: clearSessionResult.error.message,
        });
      }

      return {
        success: false,
        error: {
          code: 'token_refresh_failed',
          message: `Token refresh failed: ${refreshResult.error.message}`,
        },
      };
    }

    const userUpdateResult = await upsertOIDCUser({
      claims: refreshResult.data.claims,
      database,
      monitoring,
    });
    if (!userUpdateResult.success) {
      return {
        success: false,
        error: {
          code: 'user_update_failed',
          message: `Failed updating user from OIDC claims: ${userUpdateResult.error.message}`,
        },
      };
    }

    const sessionUpdateResult = await sessionManager.setSessionOnRequest(req, {
      auth: {
        stage: 'authenticated',
        tokens: refreshResult.data,
        userId: userUpdateResult.data.userId,
        userRole: userUpdateResult.data.userRole,
      },
      authType: 'oidc',
    });
    if (!sessionUpdateResult.success) {
      return sessionUpdateResult;
    }

    return {
      success: true,
      data: {
        userId: userUpdateResult.data.userId,
      },
    };
  });

  if (!userIdResult.success) {
    return userIdResult;
  }

  return {
    success: true,
    data: {
      userId: userIdResult.data.userId,
    },
  };
};

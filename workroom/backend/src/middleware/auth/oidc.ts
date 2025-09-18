import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { AuthManager } from '../../auth/AuthManager.js';
import type { ExpressNextFunction, ExpressRequest, ExpressResponse } from '../../interfaces.js';
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
  monitoring,
  next,
  req,
  res,
  sessionManager,
}: {
  authManager: AuthManager;
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
        return res.status(401).send('Unauthorized');
      case 'forbidden':
        await sessionManager.clearSessionForRequest(req);
        return res.status(403).send('Forbidden');
      case 'pending':
        return res.status(409).send('Conflict: Wait for auth');
      case 'expired': {
        monitoring.logger.info('OIDC access token expired');

        const refreshResult = await refreshOIDCToken({
          authManager,
          monitoring,
          req,
          sessionManager,
        });

        if (!refreshResult.success) {
          // Monitoring logs already emitted
          await sessionManager.clearSessionForRequest(req);

          return res.status(401).send('Unauthorized');
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
        monitoring.logger.error('OIDC authentication attempted but no session was found');

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

  if (!sessionResult.data.auth) {
    if (sessionResult.data.codeVerifier) {
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
    } else {
      monitoring.logger.error('OIDC authentication attempted but an empty session was provided');

      return {
        success: false,
        error: {
          code: 'forbidden',
          message: 'Session validation failed due to incomplete login',
        },
      };
    }
  }

  const authPayload = sessionResult.data.auth;

  // Validate token validity
  const validityResult = await authManager.validateTokens({ tokens: authPayload.tokens });
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
      userId: sessionResult.data.auth.tokens.userId,
    },
  };
};

export const refreshOIDCToken = async ({
  authManager,
  monitoring,
  req,
  sessionManager,
}: {
  authManager: AuthManager;
  monitoring: MonitoringContext;
  req: ExpressRequest;
  sessionManager: SessionManager;
}): Promise<Result<{ userId: string }>> => {
  const sessionResult = sessionManager.extractSessionFromRequest(req);
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
  } else if (!sessionResult.data.auth) {
    monitoring.logger.error('Unable to handle expired tokens: No tokens currently present in session');

    await sessionManager.clearSessionForRequest(req);

    return {
      success: false,
      error: {
        code: 'invalid_session',
        message: 'Invalid session: No tokens found in session',
      },
    };
  }

  const authPayload = sessionResult.data.auth;

  monitoring.logger.info('Refreshing user tokens');
  const tokensResult = await authManager.refreshSemaphore.use(authPayload.tokens.refreshToken ?? '-', async () => {
    const refreshResult = await authManager.refreshTokens({ tokens: authPayload.tokens });
    if (!refreshResult.success) {
      monitoring.logger.error('Unable to handle expired tokens: Token refresh failed', {
        errorName: refreshResult.error.code,
        errorMessage: refreshResult.error.message,
      });

      await sessionManager.clearSessionForRequest(req);

      return {
        success: false,
        error: {
          code: 'token_refresh_failed',
          message: `Token refresh failed: ${refreshResult.error.message}`,
        },
      };
    }

    await sessionManager.setSessionOnRequest(req, {
      auth: {
        tokens: refreshResult.data,
        type: 'oidc',
      },
    });

    return {
      success: true,
      data: refreshResult.data,
    };
  });

  if (!tokensResult.success) {
    return tokensResult;
  }

  return {
    success: true,
    data: {
      userId: tokensResult.data.userId,
    },
  };
};

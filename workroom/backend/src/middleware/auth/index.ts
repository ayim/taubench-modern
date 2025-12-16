import { exhaustiveCheck } from '@sema4ai/shared-utils';
import type { NextFunction, Request, Response } from 'express';
import { pathToRegexp } from 'path-to-regexp';
import { extractOIDCUserIdentity, handleOIDCAuthCheck, refreshOIDCToken } from './oidc.js';
import { extractSema4OIDCUserIdentity, handleSema4OIDCAuthCheck } from './sema4OIDC.js';
import { extractSnowflakeUserIdentity, handleSnowflakeAuthCheck } from './snowflake.js';
import type { AuthManager } from '../../auth/AuthManager.js';
import type { Permission } from '../../auth/permissions.js';
import type { Configuration } from '../../configuration.js';
import type { DatabaseClient } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/user.js';
import type { ErrorResponse } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { SessionManager } from '../../session/sessionManager.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

export const createAuthMiddleware =
  ({
    authentication,
    authManager,
    configuration,
    database,
    monitoring,
    sessionManager,
  }: {
    authentication: 'with-permissions-check' | 'without-permissions-check';
    authManager: AuthManager;
    configuration: Configuration;
    database: DatabaseClient;
    monitoring: MonitoringContext;
    sessionManager: SessionManager;
  }) =>
  async (req: Request, res: Response, next: NextFunction) => {
    switch (configuration.auth.type) {
      case 'none':
        return next();
      case 'snowflake':
        return handleSnowflakeAuthCheck({
          authentication,
          configuration,
          monitoring,
          next,
          req,
          res,
          sessionManager,
        });
      case 'sema4-oidc-sso':
        return handleSema4OIDCAuthCheck({ authentication, authManager, configuration, monitoring, next, req, res });
      case 'oidc':
        return handleOIDCAuthCheck({
          authentication,
          authManager,
          configuration,
          database,
          monitoring,
          next,
          req,
          res,
          sessionManager,
        });

      default:
        exhaustiveCheck(configuration.auth);
    }
  };

export const createAuthRedirectMiddleware =
  ({
    authManager,
    bypassedPages = [],
    configuration,
    database,
    monitoring,
    sessionManager,
  }: {
    authManager: AuthManager;
    bypassedPages: Readonly<Array<string>>;
    configuration: Configuration;
    database: DatabaseClient;
    monitoring: MonitoringContext;
    sessionManager: SessionManager;
  }) =>
  async (req: Request, res: Response, next: NextFunction) => {
    if (configuration.auth.type !== 'oidc') {
      return next();
    }

    if (!req.headers.accept?.includes('text/html')) {
      return next();
    }

    if (bypassedPages.some((pagePattern) => pathToRegexp(pagePattern).regexp.test(req.originalUrl))) {
      monitoring.logger.info('Page bypasses authentication checks', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return next();
    }

    const authResult = await extractOIDCUserIdentity({
      authManager,
      headers: extractHeadersFromRequest(req.headers),
      monitoring,
      sessionManager,
    });

    if (authResult.success) {
      return next();
    }

    switch (authResult.error.code) {
      case 'forbidden': {
        monitoring.logger.info('Received forbidden error when extracting OIDC identity: Clearing session');

        const clearResult = await sessionManager.clearSessionForRequest(req);
        if (!clearResult.success) {
          monitoring.logger.error('Failed handling forbidden authentication scenario: Failed to clear session', {
            errorName: clearResult.error.code,
            errorMessage: clearResult.error.message,
          });

          return res
            .status(500)
            .json({ error: { code: 'internal_error', message: 'Failed to handle session' } } satisfies ErrorResponse);
        }

        return res.status(403).json({ error: { code: 'forbidden', message: 'Forbidden' } } satisfies ErrorResponse);
      }
      case 'unauthorized': {
        const origin = `${req.protocol}://${req.get('host')}`;
        monitoring.logger.info('Generating redirect for origin', {
          requestUrl: origin,
        });

        const loginUrlResult = await authManager.generateLoginUrl({ origin });
        if (!loginUrlResult.success) {
          monitoring.logger.error('Failed generating login URL', {
            errorName: loginUrlResult.error.code,
            errorMessage: loginUrlResult.error.message,
          });

          return res
            .status(500)
            .json({ error: { code: 'internal_error', message: 'Internal server error' } } satisfies ErrorResponse);
        }

        await sessionManager.setSessionOnRequest(req, {
          auth: {
            codeVerifier: loginUrlResult.data.codeVerifier,
            stage: 'auth-callback',
          },
          authType: 'oidc',
        });

        return res.redirect(loginUrlResult.data.loginUrl);
      }
      case 'pending': {
        monitoring.logger.error('Invalid session state: Clearing session');

        const clearResult = await sessionManager.clearSessionForRequest(req);
        if (!clearResult.success) {
          monitoring.logger.error('Failed handling pending login: Failed clearing session', {
            errorName: clearResult.error.code,
            errorMessage: clearResult.error.message,
          });

          return res
            .status(500)
            .json({ error: { code: 'internal_error', message: 'Failed to handle session' } } satisfies ErrorResponse);
        }

        return res.redirect(307, req.originalUrl);
      }
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
          return res
            .status(500)
            .json({ error: { code: 'internal_error', message: 'Internal server error' } } satisfies ErrorResponse);
        }

        return res.redirect(307, req.originalUrl);
      }

      default:
        exhaustiveCheck(authResult.error);
    }
  };

export const extractAuthenticatedUserIdentity = async ({
  authManager,
  configuration,
  headers,
  monitoring,
  permissions,
  sessionManager,
}: {
  authManager: AuthManager;
  configuration: Configuration;
  headers: Record<string, string>;
  monitoring: MonitoringContext;
  permissions: Array<Permission>;
  sessionManager: SessionManager;
}): Promise<
  Result<
    {
      userId: string | null;
      userRole: UserRole | null;
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
    | {
        code: 'misconfigured';
        message: string;
      }
  >
> => {
  switch (configuration.auth.type) {
    case 'none':
      return {
        success: true,
        data: {
          userId: null,
          userRole: null,
        },
      };

    case 'snowflake':
      return await extractSnowflakeUserIdentity({ headers, monitoring, sessionManager });

    case 'sema4-oidc-sso': {
      const sema4SSOResult = await extractSema4OIDCUserIdentity({
        authManager,
        configuration,
        headers,
        monitoring,
        permissions,
      });
      if (!sema4SSOResult.success) {
        return sema4SSOResult;
      }

      return {
        success: true,
        data: {
          userId: sema4SSOResult.data.userId,
          userRole: null,
        },
      };
    }

    case 'oidc':
      return await extractOIDCUserIdentity({
        authManager,
        headers,
        monitoring,
        sessionManager,
      });

    default:
      exhaustiveCheck(configuration.auth);
  }
};

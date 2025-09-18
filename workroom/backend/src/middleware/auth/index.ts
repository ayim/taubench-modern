import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { NextFunction, Request, Response } from 'express';
import { pathToRegexp } from 'path-to-regexp';
import { extractGoogleUserIdentity, handleGoogleAuthCheck } from './google.js';
import { extractOIDCUserIdentity, handleOIDCAuthCheck, refreshOIDCToken } from './oidc.js';
import { extractSema4OIDCUserIdentity, handleSema4OIDCAuthCheck } from './sema4OIDC.js';
import { extractSnowflakeUserIdentity, handleSnowflakeAuthCheck } from './snowflake.js';
import type { AuthManager } from '../../auth/AuthManager.js';
import type { Permission } from '../../auth/sema4OIDC.js';
import type { Configuration } from '../../configuration.js';
import type { ErrorResponse } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { SessionManager } from '../../session/SessionManager.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

export const createAuthMiddleware =
  ({
    authentication,
    authManager,
    configuration,
    monitoring,
    sessionManager,
  }: {
    authentication: 'with-permissions-check' | 'without-permissions-check';
    authManager: AuthManager;
    configuration: Configuration;
    monitoring: MonitoringContext;
    sessionManager: SessionManager;
  }) =>
  async (req: Request, res: Response, next: NextFunction) => {
    switch (configuration.auth.type) {
      case 'none':
        return next();
      case 'google':
        return handleGoogleAuthCheck({ monitoring, next, req, res });
      case 'snowflake':
        return handleSnowflakeAuthCheck({ monitoring, next, req, res });
      case 'sema4-oidc-sso':
        return handleSema4OIDCAuthCheck({ authentication, authManager, configuration, monitoring, next, req, res });
      case 'oidc':
        return handleOIDCAuthCheck({ authManager, monitoring, next, req, res, sessionManager });

      default:
        exhaustiveCheck(configuration.auth);
    }
  };

export const createIndexAuthMiddleware =
  ({
    authManager,
    bypassedPages = [],
    configuration,
    monitoring,
    sessionManager,
  }: {
    authManager: AuthManager;
    bypassedPages: Readonly<Array<string>>;
    configuration: Configuration;
    monitoring: MonitoringContext;
    sessionManager: SessionManager;
  }) =>
  async (req: Request, res: Response, next: NextFunction) => {
    // @TODO: REMOVE AFTER DEBUG SESSION
    monitoring.logger.info('Index auth debug: Check URL', {
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });

    if (configuration.auth.type !== 'oidc') {
      // @TODO: REMOVE AFTER DEBUG SESSION
      monitoring.logger.info('Index auth debug: Auth not OIDC', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });
      return next();
    }

    if (!req.headers.accept?.includes('text/html')) {
      // @TODO: REMOVE AFTER DEBUG SESSION
      monitoring.logger.info('Index auth debug: Page not accept HTML', {
        errorMessage: JSON.stringify(req.rawHeaders),
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });
      return next();
    }

    if (bypassedPages.some((pagePattern) => pathToRegexp(pagePattern).regexp.test(req.url))) {
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
      // @TODO: REMOVE AFTER DEBUG SESSION
      monitoring.logger.info('Index auth debug: Auth success', {
        errorName: JSON.stringify(req.rawHeaders),
        errorMessage: JSON.stringify(authResult),
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });
      return next();
    }

    switch (authResult.error.code) {
      case 'forbidden':
        await sessionManager.clearSessionForRequest(req);
        return res.status(403).json({ error: { code: 'forbidden', message: 'Forbidden' } } satisfies ErrorResponse);
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
          codeVerifier: loginUrlResult.data.codeVerifier,
        });

        return res.redirect(loginUrlResult.data.loginUrl);
      }
      case 'pending': {
        monitoring.logger.error('Login is pending');

        return res
          .status(500)
          .json({ error: { code: 'internal_error', message: 'Internal server error' } } satisfies ErrorResponse);
      }
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
        },
      };
    case 'google':
      return extractGoogleUserIdentity({ headers, monitoring });
    case 'snowflake':
      return extractSnowflakeUserIdentity({ headers, monitoring });
    case 'sema4-oidc-sso':
      return await extractSema4OIDCUserIdentity({
        authManager,
        configuration,
        headers,
        monitoring,
        permissions,
      });
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

import type { ErrorResponse } from '@sema4ai/workroom-interface';
import type { AuthManager } from '../auth/AuthManager.js';
import { Roles } from '../auth/permissions.js';
import type { Configuration } from '../configuration.js';
import type { UserRole } from '../database/types/user.js';
import type { ExpressRequest, ExpressResponse, OIDCTokenClaims } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/SessionManager.js';
import { getRequestBaseUrl } from '../utils/request.js';

type AuthMeta =
  | { status: 'unauthenticated'; permissions: Array<string> }
  | {
      status: 'authenticated';
      userId: string;
      userRole: UserRole;
      permissions: Array<string>;
      claims: OIDCTokenClaims;
    };

export const createAuthMetaHandler =
  ({
    configuration,
    monitoring,
    sessionManager,
  }: {
    configuration: Configuration;
    monitoring: MonitoringContext;
    sessionManager: SessionManager;
  }) =>
  async (req: ExpressRequest, res: ExpressResponse) => {
    if (!configuration.auth.roleManagement) {
      return res.json({
        permissions: [...Roles['admin'].permissions],
        status: 'unauthenticated',
      } satisfies AuthMeta);
    }

    if (!configuration.session) {
      return res.json({
        status: 'unauthenticated',
        permissions: [],
      } satisfies AuthMeta);
    }

    const sessionResult = await sessionManager.extractSessionFromRequest(req);
    if (!sessionResult.success) {
      monitoring.logger.error('Could not extract session for auth meta', {
        errorMessage: sessionResult.error.message,
        errorName: sessionResult.error.code,
      });

      return res
        .status(500)
        .json({ error: { code: 'internal_error', message: 'Invalid authentication state' } } satisfies ErrorResponse);
    }

    res.json(
      (sessionResult.data?.auth.stage === 'authenticated'
        ? {
            claims: sessionResult.data.auth.tokens.claims,
            permissions: [...Roles[sessionResult.data.auth.userRole].permissions],
            status: 'authenticated',
            userId: sessionResult.data.auth.userId,
            userRole: sessionResult.data.auth.userRole,
          }
        : {
            permissions: [],
            status: 'unauthenticated',
          }) satisfies AuthMeta,
    );
  };

export const createLogoutHandler =
  ({
    authManager,
    configuration,
    monitoring,
    sessionManager,
  }: {
    authManager: AuthManager;
    configuration: Configuration;
    monitoring: MonitoringContext;
    sessionManager: SessionManager;
  }) =>
  async (req: ExpressRequest, res: ExpressResponse) => {
    if (!configuration.session) {
      monitoring.logger.error('Logout requested but sessions not configured');

      return res
        .status(403)
        .json({ error: { code: 'invalid_request', message: 'Bad Request' } } satisfies ErrorResponse);
    }

    const loggedOutUrl = `${getRequestBaseUrl(req)}/tenants/${configuration.tenant.tenantId}/logged-out`;

    monitoring.logger.info('Logout requested', {
      requestUrl: req.originalUrl,
    });

    const sessionResult = await sessionManager.extractSessionFromRequest(req);

    if (!sessionResult.success) {
      monitoring.logger.error('Logout attempted but session extraction failed', {
        errorName: sessionResult.error.code,
        errorMessage: sessionResult.error.message,
      });

      // TODO: replace with better error page:
      // https://linear.app/sema4ai/issue/CLOUD-5394/spar-backend-error-pages
      return res.status(500).json({
        error: {
          code: 'logout_failed',
          message: 'Failed logging out of session',
        },
      });
    }

    if (!sessionResult.data) {
      monitoring.logger.error('Logout attempted but no session present', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      // Already logged out, so redirect to the target page
      return res.redirect(loggedOutUrl);
    }

    // Session is present and we have the data, so clear it first
    monitoring.logger.info('Clear session for logout', {
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });
    const clearSessionResult = await sessionManager.clearSessionForRequest(req);
    if (!clearSessionResult.success) {
      monitoring.logger.error('Logout attempted but failed to clear session', {
        errorName: clearSessionResult.error.code,
        errorMessage: clearSessionResult.error.message,
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return res.status(500).json({
        error: {
          code: 'logout_failed',
          message: 'Failed logging out of session',
        },
      });
    }

    // Now kill the OIDC side
    if (sessionResult.data.authType === 'oidc' && sessionResult.data.auth.stage === 'authenticated') {
      monitoring.logger.info('Ending OIDC session', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      const endResult = await authManager.endSession({
        postLogoutRedirectUri: loggedOutUrl,
        tokens: sessionResult.data.auth.tokens,
      });
      if (!endResult.success) {
        monitoring.logger.error('Logout attempted but OIDC session end call failed', {
          errorName: endResult.error.code,
          errorMessage: endResult.error.message,
          requestMethod: req.method,
          requestUrl: req.originalUrl,
        });

        return res.redirect(loggedOutUrl);
      }

      // Nothing else left to do apart from redirect
      return res.redirect(endResult.data.logoutUri);
    }

    return res.redirect(loggedOutUrl);
  };

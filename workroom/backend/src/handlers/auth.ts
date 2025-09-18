import type { ErrorResponse } from '@sema4ai/workroom-interface';
import type { AuthManager } from '../auth/AuthManager.js';
import type { Configuration } from '../configuration.js';
import type { ExpressRequest, ExpressResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/SessionManager.js';
import { getRequestBaseUrl } from '../utils/request.js';

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

    const sessionResult = sessionManager.extractSessionFromRequest(req);
    if (!sessionResult.success) {
      monitoring.logger.error('Logout attempted but no session present', {
        requestUrl: req.originalUrl,
      });

      // Already logged out, so redirect to the target page
      return res.redirect(loggedOutUrl);
    }
    if (!sessionResult.data.auth) {
      monitoring.logger.error('Logout attempted but incomplete session found', {
        requestUrl: req.originalUrl,
      });

      await sessionManager.clearSessionForRequest(req);

      return res.redirect(loggedOutUrl);
    }

    // Session is present and we have the data, so clear it first
    await sessionManager.clearSessionForRequest(req);

    // Now kill the OIDC side
    const endResult = await authManager.endSession({
      postLogoutRedirectUri: loggedOutUrl,
      tokens: sessionResult.data.auth.tokens,
    });
    if (!endResult.success) {
      monitoring.logger.error('Logout attempted but OIDC session end call failed', {
        errorName: endResult.error.code,
        errorMessage: endResult.error.message,
      });

      return res.redirect(loggedOutUrl);
    }

    // Nothing else left to do apart from redirect
    return res.redirect(endResult.data.logoutUri);
  };

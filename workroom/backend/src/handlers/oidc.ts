import z from 'zod';
import type { AuthManager } from '../auth/AuthManager.js';
import type { Configuration } from '../configuration.js';
import type { ErrorResponse, ExpressRequest, ExpressResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/SessionManager.js';

export const createOIDCCallbackHandler =
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
    monitoring.logger.info('Login callback received');

    if (configuration.auth.type !== 'oidc') {
      return res.status(404).json({ error: { code: 'not_found', message: 'Not found' } } satisfies ErrorResponse);
    }

    const queryResult = z
      .object({
        code: z.string().nonempty(),
        state: z.string().nonempty(),
      })
      .safeParse(req.query);
    if (!queryResult.success) {
      monitoring.logger.error('Bad OIDC callback: Invalid query data', {
        error: queryResult.error,
      });

      // Try to clear the session as we're in an error state - don't check
      // the result as it most likely doesn't matter
      await sessionManager.clearSessionForRequest(req);

      return res
        .status(403)
        .json({ error: { code: 'invalid_request', message: 'Bad Request' } } satisfies ErrorResponse);
    }

    const sessionData = await sessionManager.extractSessionFromRequest(req);

    if (!sessionData.success) {
      monitoring.logger.error('OIDC callback failed: session extraction failed', {
        errorName: sessionData.error.code,
        errorMessage: sessionData.error.message,
      });

      return res.status(500).json({
        error: { code: 'internal_error', message: 'Callback failed due to session handling failure' },
      } satisfies ErrorResponse);
    }

    if (!sessionData.data) {
      monitoring.logger.error('Bad OIDC callback: No session data found');

      return res.status(401).json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
    }

    if (sessionData.data.authType !== 'oidc') {
      monitoring.logger.error('Bad OIDC callback: Session authentication not currently in OIDC mode');

      return res.status(400).json({
        error: { code: 'invalid_request', message: 'Invalid request for this configuration' },
      } satisfies ErrorResponse);
    }
    if (sessionData.data.auth.stage !== 'auth-callback') {
      monitoring.logger.error('Bad OIDC callback: Session not ready for callback or already authenticated');

      return res.status(400).json({
        error: { code: 'invalid_request', message: 'Invalid request for this session' },
      } satisfies ErrorResponse);
    }

    const { codeVerifier } = sessionData.data.auth;
    // Clear session state - soft delete
    await sessionManager.setSessionOnRequest(req, null);

    const { code, state } = queryResult.data;
    const origin = `${req.protocol}://${req.get('host')}`;
    const redirectUri = `${origin}/tenants/${configuration.tenant.tenantId}/workroom/oidc/callback`;

    const tokensResult = await authManager.exchangeCodeForTokens({
      code,
      codeVerifier,
      redirectUri,
      state,
    });

    if (!tokensResult.success) {
      monitoring.logger.error('Token exchange failed', {
        errorName: tokensResult.error.code,
        errorMessage: tokensResult.error.message,
      });

      return {
        success: false,
        error: {
          code: 'token_exchange_failed',
          message: `Failed exchanging code for tokens: ${tokensResult.error.message}`,
        },
      };
    }

    await sessionManager.setSessionOnRequest(req, {
      auth: {
        stage: 'authenticated',
        tokens: tokensResult.data,
      },
      authType: 'oidc',
    });

    monitoring.logger.info('User logged in successfully');

    res.redirect(`/tenants/${configuration.tenant.tenantId}/home`);
  };

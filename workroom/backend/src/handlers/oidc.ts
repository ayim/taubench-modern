import z from 'zod';
import type { AuthManager } from '../auth/AuthManager.js';
import type { Configuration } from '../configuration.js';
import type { ExpressRequest, ExpressResponse } from '../interfaces.js';
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
      return res.status(404).send('Not found');
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

      await sessionManager.clearSessionForRequest(req);

      return res.status(400).send('Bad request');
    }

    const sessionData = sessionManager.extractSessionFromRequest(req);
    if (!sessionData.success) {
      monitoring.logger.error('Bad OIDC callback: No session data found', {
        errorName: sessionData.error.code,
        errorMessage: sessionData.error.message,
      });

      return res.status(401).send('Unauthorized');
    }
    if (!sessionData.data.codeVerifier) {
      monitoring.logger.error('Bad OIDC callback: No code verifier found');

      return res.status(403).send('Forbidden');
    }

    const { codeVerifier } = sessionData.data;
    // Clear session state
    await sessionManager.setSessionOnRequest(req, {});

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
        tokens: tokensResult.data,
        type: 'oidc',
      },
    });

    monitoring.logger.info('User logged in successfully');

    res.redirect(`/tenants/${configuration.tenant.tenantId}/home`);
  };

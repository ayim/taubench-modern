import type {
  Configuration as ClientConfiguration,
  DiscoveryRequestOptions,
  IDToken,
  TokenEndpointResponse,
  TokenEndpointResponseHelpers,
} from 'openid-client';
import * as oidcClient from 'openid-client';
import type { Configuration } from '../configuration.js';
import type { LogAttributes, MonitoringContext } from '../monitoring/index.js';
import { safeParseUrl } from '../utils/url.js';

export interface OIDCClientOptions {
  clientId: string;
  clientSecret: string;
  serverUrl: string;
}

export interface OIDCPKCEChallenge {
  codeChallenge: string;
  codeVerifier: string;
}

const extractLogDetailsForOIDCError = (
  err: oidcClient.AuthorizationResponseError | oidcClient.ResponseBodyError,
): Partial<LogAttributes> => {
  return {
    errorCause: err.cause ? err.cause.toString() : undefined,
    errorMessage: err.error_description ? `${err.message}: ${err.error_description}` : err.message,
    errorName: err.name,
    errorStack: err.stack,
  };
};

export class OIDCClient {
  private monitoring: MonitoringContext;
  private oidcClientConfiguration: ClientConfiguration;
  private scopes: Array<string>;

  constructor({
    monitoring,
    oidcClientConfiguration,
    scopes,
  }: {
    monitoring: MonitoringContext;
    oidcClientConfiguration: ClientConfiguration;
    scopes: Array<string>;
  }) {
    this.monitoring = monitoring;
    this.oidcClientConfiguration = oidcClientConfiguration;
    this.scopes = scopes;
  }

  async exchangeCodeForTokens({
    code,
    codeVerifier,
    redirectUri,
  }: {
    code: string;
    redirectUri: string;
    codeVerifier: string;
  }): Promise<{
    idTokenClaims: IDToken | undefined;
    response: TokenEndpointResponse & TokenEndpointResponseHelpers;
  }> {
    const tokenSet = await (async () => {
      try {
        return await oidcClient.authorizationCodeGrant(
          this.oidcClientConfiguration,
          new URL(`${redirectUri}?code=${code}`),
          {
            pkceCodeVerifier: codeVerifier,
          },
        );
      } catch (err) {
        if (err instanceof oidcClient.AuthorizationResponseError || err instanceof oidcClient.ResponseBodyError) {
          this.monitoring.logger.error('OIDC token exchange authorization error', extractLogDetailsForOIDCError(err));
        } else {
          this.monitoring.logger.error('OIDC token exchange error', {
            error: err as Error,
          });
        }

        throw err;
      }
    })();

    const idTokenClaims = tokenSet.claims();
    this.monitoring.logger.debug('Exchanged OIDC token', {
      oidcClaims: JSON.stringify(idTokenClaims ?? {}),
      oidcHasRefresh: !!tokenSet.refresh_token,
    });

    return {
      idTokenClaims,
      response: tokenSet,
    };
  }

  async getAuthorizationUrl({
    codeChallenge,
    redirectUri,
    state,
  }: {
    codeChallenge: string;
    redirectUri: string;
    state: string;
  }): Promise<string> {
    const authParams: Record<string, string> = {
      redirect_uri: redirectUri,
      state,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256',
    };

    const issuerUrlResult = safeParseUrl(this.oidcClientConfiguration.serverMetadata().issuer);
    if (!issuerUrlResult.success) {
      throw new Error(`Failed parsing OIDC issuer URL: ${issuerUrlResult.error.message}`);
    }

    if (issuerUrlResult.data.host === 'accounts.google.com') {
      // Google handles offline access (refresh tokens) differently, so we cannot specify the
      // 'offline_access' scope, and instead need to use non-standard parameters:
      this.scopes = this.scopes.filter((scope) => scope !== 'offline_access');
      authParams.access_type = 'offline';
      // We need to force the consent screen if we want refresh tokens. Since we reuse
      // Google client IDs, we cannot ensure that a user has not already consented
      // against a client ID on another app instance, thus potentially resulting in
      // us not having a refresh token for this login - sad path. We want to ensure that
      // we always do, because a little time spent consenting now means a more streamlined
      // experience later.
      authParams.prompt = 'consent';
    }

    authParams.scope = this.scopes.join(' ');

    const authUrl = oidcClient.buildAuthorizationUrl(this.oidcClientConfiguration, authParams);

    this.monitoring.logger.info('Generated OIDC authorization URL', {
      oidcIssuer: issuerUrlResult.data.toString(),
      oidcScopes: authParams.scope,
      requestUrl: authUrl.toString(),
    });

    return authUrl.href;
  }

  async getEndSessionUrl({
    idToken,
    postLogoutRedirectUri,
    state,
  }: {
    idToken: string | null;
    postLogoutRedirectUri: string;
    state: string;
  }): Promise<string> {
    const params: {
      id_token_hint?: string;
      post_logout_redirect_uri: string;
      state: string;
    } = {
      post_logout_redirect_uri: postLogoutRedirectUri,
      state: state,
    };

    if (idToken) {
      params.id_token_hint = idToken;
    }

    const endSessionUrl = oidcClient.buildEndSessionUrl(this.oidcClientConfiguration, params);

    return endSessionUrl.href;
  }

  async refreshTokens({
    refreshToken,
  }: {
    refreshToken: string;
  }): Promise<TokenEndpointResponse & TokenEndpointResponseHelpers> {
    const tokenSet = await (async () => {
      try {
        const tokens = await oidcClient.refreshTokenGrant(this.oidcClientConfiguration, refreshToken);

        if (!tokens.refresh_token) {
          // Google, and some other providers, don't issue refresh tokens if:
          //   - The exchange is not the first, and
          //   - No consent screen is shown
          // In this case we need to reuse the refresh token, which doesn't necessarily expire
          (tokens as { refresh_token: string }).refresh_token = refreshToken;
        }

        return tokens;
      } catch (err) {
        if (err instanceof oidcClient.AuthorizationResponseError || err instanceof oidcClient.ResponseBodyError) {
          this.monitoring.logger.error('OIDC token refresh authorization error', extractLogDetailsForOIDCError(err));
        } else {
          this.monitoring.logger.error('OIDC token refresh error', {
            error: err as Error,
          });
        }

        throw err;
      }
    })();

    const idToken = tokenSet.claims();
    this.monitoring.logger.debug('Refreshed OIDC token', {
      oidcClaims: JSON.stringify(idToken ?? {}),
      oidcHasRefresh: !!tokenSet.refresh_token,
    });

    return tokenSet;
  }

  async revokeToken({
    token,
    tokenType,
  }: {
    token: string;
    tokenType: 'access_token' | 'refresh_token';
  }): Promise<void> {
    await oidcClient.tokenRevocation(this.oidcClientConfiguration, token, {
      token_type_hint: tokenType,
    });
  }

  // #region Static
  static async discover({
    configuration,
    monitoring,
  }: {
    configuration: Configuration;
    monitoring: MonitoringContext;
  }): Promise<OIDCClient> {
    if (configuration.auth.type !== 'oidc') {
      throw new Error(`Failed configuring OIDC client via discovery: Invalid auth type: ${configuration.auth.type}`);
    }

    monitoring.logger.info('Discovering OIDC provider', {
      requestUrl: configuration.auth.oidcServer,
    });

    const discoveryOptions: DiscoveryRequestOptions = {};
    if (configuration.allowInsecureRequests) {
      monitoring.logger.info('Configuration allows for insecure authentication requests');

      discoveryOptions.execute = [oidcClient.allowInsecureRequests];
    }

    const config = await oidcClient.discovery(
      new URL(configuration.auth.oidcServer),
      configuration.auth.clientId,
      configuration.auth.clientSecret,
      undefined,
      discoveryOptions,
    );

    monitoring.logger.info('Configured OIDC provider', {
      oidcIssuer: config.serverMetadata().issuer,
    });

    return new OIDCClient({
      monitoring,
      oidcClientConfiguration: config,
      scopes: configuration.auth.scopes,
    });
  }

  static extractUserIdFromClaims(claims: IDToken): string {
    if (!claims.sub) {
      throw new Error('Unexpected error: failed retrieving sub from OIDC token claims: sub field is not specified');
    }

    return claims.sub;
  }

  static async generatePKCE(): Promise<OIDCPKCEChallenge> {
    const codeVerifier = oidcClient.randomPKCECodeVerifier();
    const codeChallenge = await oidcClient.calculatePKCECodeChallenge(codeVerifier);

    return { codeVerifier, codeChallenge };
  }

  /**
   * Returns a JavaScript timestamp for when a token expiry is to occur
   */
  static resolveExpiresAt(expiresInSec: number | undefined): number {
    if (typeof expiresInSec === 'undefined' || !(expiresInSec > 0)) {
      return Date.now() - 1;
    }

    return Date.now() + expiresInSec * 1000;
  }
  // #endregion
}

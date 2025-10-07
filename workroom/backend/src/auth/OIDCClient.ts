import type {
  Configuration as ClientConfiguration,
  DiscoveryRequestOptions,
  IDToken,
  TokenEndpointResponse,
  TokenEndpointResponseHelpers,
} from 'openid-client';
import * as oidcClient from 'openid-client';
import z from 'zod';
import type { Configuration } from '../configuration.js';
import type { MonitoringContext } from '../monitoring/index.js';
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

const emailSchema = z.string().email();

export class OIDCClient {
  private monitoring: MonitoringContext;
  private oidcClientConfiguration: ClientConfiguration;

  constructor({
    monitoring,
    oidcClientConfiguration,
  }: {
    monitoring: MonitoringContext;
    oidcClientConfiguration: ClientConfiguration;
  }) {
    this.monitoring = monitoring;
    this.oidcClientConfiguration = oidcClientConfiguration;
  }

  async exchangeCodeForTokens({
    code,
    codeVerifier,
    redirectUri,
  }: {
    code: string;
    redirectUri: string;
    codeVerifier: string;
  }): Promise<TokenEndpointResponse & TokenEndpointResponseHelpers> {
    const tokenSet = await oidcClient.authorizationCodeGrant(
      this.oidcClientConfiguration,
      new URL(`${redirectUri}?code=${code}`),
      {
        pkceCodeVerifier: codeVerifier,
      },
    );

    return tokenSet;
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
      authParams.scope = 'openid email';
      authParams.access_type = 'offline';
    } else {
      // Required scopes:
      //  email           => Email address sub
      //  offline_access  => Refresh tokens
      //  openid          => ID tokens
      authParams.scope = 'openid email offline_access';
    }

    const authUrl = oidcClient.buildAuthorizationUrl(this.oidcClientConfiguration, authParams);

    this.monitoring.logger.info('Generated OIDC authorization URL', {
      oidcIssuer: issuerUrlResult.data.toString(),
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
    const tokenSet = await oidcClient.refreshTokenGrant(this.oidcClientConfiguration, refreshToken);

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
    });
  }

  static extractUserIdFromClaims(claims: IDToken): string {
    const isEmail = (value: unknown) => emailSchema.safeParse(value).success;

    if (isEmail(claims.sub)) return claims.sub;
    if (claims['email']) {
      if (!isEmail(claims['email'])) {
        throw new Error(`Invalid email claim: Invalid email address: ${claims['email']}`);
      }

      // @TODO: Handle other types correctly
      return claims['email'] as string;
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

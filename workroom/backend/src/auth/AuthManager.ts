import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { Configuration } from '../configuration.js';
import { OIDCClient } from './OIDCClient.js';
import { createGetACEUser, type GetACEUser, type UserFrom } from './sema4OIDC.js';
import type { Tokens } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { asResult, type Result } from '../utils/result.js';
import { Semaphore } from './utils/Semaphore.js';
import { safeParseUrl } from '../utils/url.js';

export type EndSessionResult = Result<{ logoutUri: string }>;

export type TokenRefreshResult = Result<
  Tokens,
  {
    code: 'no_refresh_token' | 'failed' | 'invalid_configuration';
    message: string;
  }
>;

export type TokenValidationResult = Result<
  void,
  {
    code: 'expired';
    message: string;
  }
>;

export class AuthManager {
  private configuration: Configuration;
  private monitoring: MonitoringContext;

  private getACEUser: GetACEUser | null = null;
  private oidcClient: OIDCClient | null = null;

  public readonly refreshSemaphore: Semaphore<Result<Tokens>>;

  constructor({ configuration, monitoring }: { configuration: Configuration; monitoring: MonitoringContext }) {
    this.configuration = configuration;
    this.monitoring = monitoring;

    this.refreshSemaphore = new Semaphore<Result<Tokens>>();
  }

  async endSession({
    postLogoutRedirectUri,
    tokens,
  }: {
    postLogoutRedirectUri: string;
    tokens: Tokens;
  }): Promise<EndSessionResult> {
    this.monitoring.logger.info('Ending session', {
      authMode: this.configuration.auth.type,
    });

    switch (this.configuration.auth.type) {
      case 'google':
      case 'none':
      case 'sema4-oidc-sso':
      case 'snowflake':
        return {
          success: false,
          error: {
            code: 'unsupported_end_session',
            message: `Session end is not supported with auth type: ${this.configuration.auth.type}`,
          },
        };

      case 'oidc': {
        if (!this.oidcClient) {
          return {
            success: false,
            error: {
              code: 'no_oidc_client',
              message: 'Invalid configuration: No OIDC client present',
            },
          };
        }

        try {
          // Revoke tokens
          await this.oidcClient.revokeToken({
            token: tokens.accessToken,
            tokenType: 'access_token',
          });

          if (tokens.refreshToken) {
            await this.oidcClient.revokeToken({
              token: tokens.refreshToken,
              tokenType: 'refresh_token',
            });
          }

          const logoutUri = await this.oidcClient.getEndSessionUrl({
            idToken: tokens.idToken,
            postLogoutRedirectUri,
            state: tokens.state,
          });

          return {
            success: true,
            data: {
              logoutUri,
            },
          };
        } catch (err) {
          this.monitoring.logger.error('Logout failed for OIDC session', {
            error: err as Error,
          });

          return {
            success: false,
            error: {
              code: 'logout_failed',
              message: `Logout failed: ${(err as Error).message}`,
            },
          };
        }
      }

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  async exchangeCodeForTokens({
    code,
    codeVerifier,
    redirectUri,
    state,
  }: {
    code: string;
    codeVerifier: string;
    redirectUri: string;
    state: string;
  }): Promise<Result<Tokens>> {
    switch (this.configuration.auth.type) {
      case 'google':
      case 'none':
      case 'sema4-oidc-sso':
      case 'snowflake':
        return {
          success: false,
          error: {
            code: 'unsupported_token_exchange',
            message: `OIDC token exchange not supported for auth type: ${this.configuration.auth.type}`,
          },
        };

      case 'oidc': {
        return await asResult(async () => {
          if (!this.oidcClient) {
            return {
              success: false,
              error: {
                code: 'no_oidc_client',
                message: 'Invalid configuration: No OIDC client present',
              },
            };
          }
          const response = await this.oidcClient.exchangeCodeForTokens({ code, codeVerifier, redirectUri });

          if (!response.id_token) {
            // Should not occur so long as:
            //  - openid scope is present
            //  - response_type=code
            //  - not using client credentials flow
            this.monitoring.logger.info('No ID token for token exchange');
          }

          const claims = response.claims();
          if (!claims) {
            throw new Error('No claims returned for token exchange');
          }

          const userId = OIDCClient.extractUserIdFromClaims(claims);

          return {
            success: true,
            data: {
              accessToken: response.access_token,
              expiresAt: OIDCClient.resolveExpiresAt(response.expiresIn()),
              idToken: response.id_token ?? null,
              refreshToken: response.refresh_token ?? null,
              state,
              tokenType: response.token_type,
              userId,
            },
          };
        });
      }

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  async generateLoginUrl({ origin }: { origin: string }): Promise<
    Result<{
      codeVerifier: string;
      loginUrl: string;
    }>
  > {
    switch (this.configuration.auth.type) {
      case 'google':
      case 'none':
      case 'sema4-oidc-sso':
      case 'snowflake':
        return {
          success: false,
          error: {
            code: 'unsupported_login_url_generation',
            message: `Login URL generation not supported for auth type: ${this.configuration.auth.type}`,
          },
        };

      case 'oidc': {
        if (!this.oidcClient) {
          return {
            success: false,
            error: {
              code: 'no_oidc_client',
              message: 'Invalid configuration: No OIDC client present',
            },
          };
        }

        const redirectUrlResult = safeParseUrl(origin);
        if (!redirectUrlResult.success) {
          return {
            success: false,
            error: {
              code: 'invalid_request_origin',
              message: `Request origin invalid: ${redirectUrlResult.error.message}`,
            },
          };
        }

        try {
          const pkce = await OIDCClient.generatePKCE();

          const redirectUrl = redirectUrlResult.data;
          redirectUrl.pathname = `/tenants/${this.configuration.tenant.tenantId}/workroom/oidc/callback`;

          this.monitoring.logger.info('Generating login URL for origin', {
            oidcRedirectUrl: redirectUrl.toString(),
          });

          const url = await this.oidcClient.getAuthorizationUrl({
            codeChallenge: pkce.codeChallenge,
            redirectUri: redirectUrl.toString(),
          });

          return {
            success: true,
            data: {
              codeVerifier: pkce.codeVerifier,
              loginUrl: url,
            },
          };
        } catch (err) {
          this.monitoring.logger.error('OIDC failed discovery', {
            error: err as Error,
          });

          return {
            success: false,
            error: {
              code: 'oidc_discovery_failed',
              message: 'OIDC discovery request failed',
            },
          };
        }
      }
    }
  }

  async initialize(): Promise<Result<void>> {
    switch (this.configuration.auth.type) {
      case 'none':
      case 'google':
      case 'snowflake':
        return { success: true, data: undefined };

      case 'sema4-oidc-sso': {
        const { getACEUser } = createGetACEUser({
          configuration: this.configuration,
          monitoring: this.monitoring,
        });

        this.getACEUser = getACEUser;

        return { success: true, data: undefined };
      }

      case 'oidc':
        try {
          this.oidcClient = await OIDCClient.discover({
            configuration: this.configuration,
            monitoring: this.monitoring,
          });

          return { success: true, data: undefined };
        } catch (err) {
          this.monitoring.logger.error('OIDC failed discovery', {
            error: err as Error,
          });

          return {
            success: false,
            error: {
              code: 'oidc_discovery_failed',
              message: 'OIDC discovery request failed',
            },
          };
        }

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  async refreshTokens({ tokens }: { tokens: Tokens }): Promise<TokenRefreshResult> {
    switch (this.configuration.auth.type) {
      case 'oidc': {
        if (!this.oidcClient) {
          return {
            success: false,
            error: {
              code: 'invalid_configuration',
              message: 'Invalid configuration: No OIDC client present',
            },
          };
        }

        if (!tokens.refreshToken) {
          return {
            success: false,
            error: {
              code: 'no_refresh_token',
              message: 'No refresh token in token set',
            },
          };
        }

        let newTokens: Tokens;
        try {
          const response = await this.oidcClient.refreshTokens({ refreshToken: tokens.refreshToken });

          const claims = response.claims();
          if (!claims) {
            throw new Error('No claims returned for token exchange');
          }

          const userId = OIDCClient.extractUserIdFromClaims(claims);

          newTokens = {
            accessToken: response.access_token,
            expiresAt: OIDCClient.resolveExpiresAt(response.expiresIn()),
            idToken: response.id_token ?? null,
            refreshToken: response.refresh_token ?? null,
            state: tokens.state,
            tokenType: response.token_type,
            userId,
          };
        } catch (err) {
          this.monitoring.logger.error('Token refresh request failed', {
            error: err as Error,
          });

          return {
            success: false,
            error: {
              code: 'failed',
              message: 'Token refresh failed',
            },
          };
        }

        return {
          success: true,
          data: newTokens,
        };
      }
      case 'sema4-oidc-sso':
      case 'google':
      case 'none':
      case 'snowflake':
        this.monitoring.logger.error(
          `Unexpected error refreshing tokens: Bad configuration: Auth type not supported for token refresh: ${this.configuration.auth.type}`,
        );

        return {
          success: false,
          error: {
            code: 'invalid_configuration',
            message: `Failed refreshing tokens: Auth type not supported for token refresh: ${this.configuration.auth.type}`,
          },
        };

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  async resolveUserId(userFrom: UserFrom): Promise<Result<string>> {
    switch (this.configuration.auth.type) {
      case 'sema4-oidc-sso': {
        if (!this.getACEUser) {
          this.monitoring.logger.error('Unexpected error resolving ACE user: Missing getACEUser function');

          return {
            success: false,
            error: {
              code: 'invalid_configuration',
              message: 'Failed resolving ACE user: No getACEUser function defined',
            },
          };
        }

        const result = await this.getACEUser(userFrom);
        if (!result.success) {
          return result;
        }

        return {
          success: true,
          data: result.data.userId,
        };
      }

      case 'google':
      case 'none':
      case 'snowflake':
      case 'oidc':
        this.monitoring.logger.error(
          `Unexpected error resolving ACE user: Bad configuration: Auth type not supported for user resolution: ${this.configuration.auth.type}`,
        );

        return {
          success: false,
          error: {
            code: 'invalid_configuration',
            message: `Failed resolving ACE user: Auth type not supported for user resolution: ${this.configuration.auth.type}`,
          },
        };

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  async validateTokens({ tokens }: { tokens: Tokens }): Promise<TokenValidationResult> {
    if (tokens.expiresAt <= Date.now()) {
      return {
        success: false,
        error: {
          code: 'expired',
          message: 'Access token is expired',
        },
      };
    }

    return {
      success: true,
      data: undefined,
    };
  }
}

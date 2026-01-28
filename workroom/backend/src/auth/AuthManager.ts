import { asResult, exhaustiveCheck, type Result } from '@sema4ai/shared-utils';
import type { Configuration } from '../configuration.js';
import { OIDCClient } from './OIDCClient.js';
import type { UserIdentity } from '../database/types/userIdentity.js';
import { OIDCTokenClaims, type OIDCTokens } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { Semaphore } from './utils/Semaphore.js';
import { OIDCAuthState } from '../utils/schemas.js';
import { SNOWFLAKE_AUTHORITY } from '../utils/snowflake.js';
import { safeParseUrl } from '../utils/url.js';

export type EndSessionResult = Result<{ logoutUri: string }>;

export type TokenRefreshResult = Result<
  OIDCTokens,
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

  private oidcClient: OIDCClient | null = null;

  public readonly refreshSemaphore: Semaphore<Result<{ userId: string }>>;

  constructor({ configuration, monitoring }: { configuration: Configuration; monitoring: MonitoringContext }) {
    this.configuration = configuration;
    this.monitoring = monitoring;

    this.refreshSemaphore = new Semaphore<Result<{ userId: string }>>();
  }

  async endSession({
    postLogoutRedirectUri,
    tokens,
  }: {
    postLogoutRedirectUri: string;
    tokens: OIDCTokens;
  }): Promise<EndSessionResult> {
    this.monitoring.logger.info('Ending session', {
      authMode: this.configuration.auth.type,
    });

    switch (this.configuration.auth.type) {
      case 'none':
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
  }): Promise<Result<OIDCTokens>> {
    switch (this.configuration.auth.type) {
      case 'none':
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
          const { idTokenClaims, response } = await this.oidcClient.exchangeCodeForTokens({
            code,
            codeVerifier,
            redirectUri,
          });

          if (!response.id_token) {
            // Should not occur so long as:
            //  - openid scope is present
            //  - response_type=code
            //  - not using client credentials flow
            this.monitoring.logger.info('No ID token for token exchange');
          }

          // Validate state
          try {
            const raw = JSON.parse(Buffer.from(state, 'base64').toString());
            OIDCAuthState.parse(raw);
          } catch (err) {
            this.monitoring.logger.error('Error validating OIDC callback state', {
              error: err as Error,
            });

            throw err;
          }

          if (!idTokenClaims || !response.id_token) {
            throw new Error('No claims returned for token exchange');
          }

          const userId = OIDCClient.extractUserIdFromClaims(idTokenClaims);

          return {
            success: true,
            data: {
              accessToken: response.access_token,
              claims: OIDCTokenClaims.parse(idTokenClaims),
              expiresAt: OIDCClient.resolveExpiresAt(response.expiresIn()),
              idToken: response.id_token,
              oidcUserId: userId,
              refreshToken: response.refresh_token ?? null,
              state,
              tokenType: response.token_type,
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
      case 'none':
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

        try {
          const pkce = await OIDCClient.generatePKCE();

          const redirectUrlsResult = this.generateRedirectURLs({ origin });
          if (!redirectUrlsResult.success) {
            return redirectUrlsResult;
          }

          const { redirectUrl, state } = ((): { redirectUrl: string; state: string } => {
            if (redirectUrlsResult.data.type === 'intermediary') {
              return {
                redirectUrl: redirectUrlsResult.data.intermediate.toString(),
                state: Buffer.from(
                  JSON.stringify({
                    returnTo: redirectUrlsResult.data.final,
                  } satisfies OIDCAuthState),
                ).toString('base64'),
              };
            }

            return {
              redirectUrl: redirectUrlsResult.data.url,
              state: Buffer.from(
                JSON.stringify({
                  returnTo: redirectUrlsResult.data.url,
                } satisfies OIDCAuthState),
              ).toString('base64'),
            };
          })();

          this.monitoring.logger.info('Generating login URL for origin', {
            oidcRedirectUrl: redirectUrl.toString(),
          });

          const url = await this.oidcClient.getAuthorizationUrl({
            codeChallenge: pkce.codeChallenge,
            redirectUri: redirectUrl,
            state,
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

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  generateRedirectURLs({
    origin,
  }: {
    origin: string;
  }): Result<{ type: 'single'; url: string } | { type: 'intermediary'; intermediate: string; final: string }> {
    switch (this.configuration.auth.type) {
      case 'none':
      case 'snowflake':
        return {
          success: false,
          error: {
            code: 'unsupported_login_url_generation',
            message: `Login URL generation not supported for auth type: ${this.configuration.auth.type}`,
          },
        };

      case 'oidc': {
        const redirectUrlResult = safeParseUrl(origin);
        if (!redirectUrlResult.success) {
          return {
            success: false,
            error: {
              code: 'invalid_redirect_url',
              message: `Redirect URL invalid: ${redirectUrlResult.error.message}`,
            },
          };
        }

        const targetReturnPath = `/tenants/${this.configuration.tenant.tenantId}/workroom/oidc/callback`;

        const finalRedirectUrl = redirectUrlResult.data;
        finalRedirectUrl.pathname = targetReturnPath;

        const intermediaryRedirectUrl =
          (this.configuration.auth.type == 'oidc' && this.configuration.auth.intermediaryCallbackRedirectUrl) || null;

        if (intermediaryRedirectUrl) {
          const intermediaryUrlResult = safeParseUrl(intermediaryRedirectUrl);
          if (!intermediaryUrlResult.success) {
            return {
              success: false,
              error: {
                code: 'invalid_redirect_url',
                message: `Intermediary redirect URL invalid: ${intermediaryUrlResult.error.message}`,
              },
            };
          }

          const intermediaryUrl = intermediaryUrlResult.data;
          intermediaryUrl.pathname = '/callback';

          return {
            success: true,
            data: {
              final: finalRedirectUrl.toString(),
              intermediate: intermediaryUrl.toString(),
              type: 'intermediary',
            },
          };
        }

        return {
          success: true,
          data: {
            type: 'single',
            url: finalRedirectUrl.toString(),
          },
        };
      }

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  getAuthorityMetadata(): Result<{
    authority: UserIdentity['authority'];
    type: UserIdentity['type'];
  }> {
    switch (this.configuration.auth.type) {
      case 'oidc':
        if (!this.oidcClient) {
          return {
            success: false,
            error: {
              code: 'invalid_configuration',
              message: 'Invalid configuration: No OIDC client present',
            },
          };
        }

        return {
          success: true,
          data: {
            authority: this.oidcClient.getIssuer(),
            type: 'oidc_sub',
          },
        };

      case 'snowflake':
        return {
          success: true,
          data: {
            authority: SNOWFLAKE_AUTHORITY,
            type: 'snowflake_user_header',
          },
        };

      case 'none':
        return {
          success: false,
          error: {
            code: 'unsupported_authority_configuration',
            message: `Invalid authentication configuration for fetching authority: ${this.configuration.auth.type}`,
          },
        };

      default:
        exhaustiveCheck(this.configuration.auth);
    }
  }

  async initialize(): Promise<Result<void>> {
    switch (this.configuration.auth.type) {
      case 'none':
      case 'snowflake':
        return { success: true, data: undefined };

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

  async refreshTokens({ tokens }: { tokens: OIDCTokens }): Promise<TokenRefreshResult> {
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

        let newTokens: OIDCTokens;
        try {
          const response = await this.oidcClient.refreshTokens({ refreshToken: tokens.refreshToken });

          const claims = response.claims();
          if (!claims || !response.id_token) {
            throw new Error('No claims returned for token exchange');
          }

          const oidcUserId = OIDCClient.extractUserIdFromClaims(claims);

          newTokens = {
            accessToken: response.access_token,
            claims: OIDCTokenClaims.parse(claims),
            expiresAt: OIDCClient.resolveExpiresAt(response.expiresIn()),
            idToken: response.id_token,
            oidcUserId,
            refreshToken: response.refresh_token ?? null,
            state: tokens.state,
            tokenType: response.token_type,
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

  async validateTokens({ tokens }: { tokens: OIDCTokens }): Promise<TokenValidationResult> {
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

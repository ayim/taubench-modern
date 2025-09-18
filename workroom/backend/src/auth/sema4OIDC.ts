import TTLCache from '@isaacs/ttlcache';
import { expectedValue, getTokenVerifier, keyPairHelpers } from '@sema4ai/robocloud-auth-utils';
import { SignInterface, type WorkRoomV1 } from '@sema4ai/robocloud-sign-interface';
import type { Configuration } from '../configuration.js';
import type { AuthManager } from './AuthManager.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { formatZodError } from '../utils/error.js';
import type { Result } from '../utils/result.js';
import { ControlPlaneUserResponse } from '../utils/schemas.js';
import { joinUrl } from '../utils/url.js';

// #region Interfaces
export type UserFrom =
  | {
      type: 'identities';
      value: { type: 'sema4_sso' | 'email' | 'microsoft_oid' | 'slack_user_id'; value: string }[];
    }
  | {
      type: 'aceUserId';
      value: string;
    };

export type GetACEUser = (userFrom: UserFrom) => Promise<Result<{ userId: string }>>;

export type WorkroomUser = WorkRoomV1;
export type Permission = WorkRoomV1['capabilities']['byTenantId'][string][number];
// #endregion

// #region Helpers
type IdentityHashCacheKey = string;

const getIdentityKey = (identity: Extract<UserFrom, { type: 'identities' }>['value'][number]) =>
  `${identity.type}:${identity.value}`;

const getIdentityHashCacheKey = (
  identities: Extract<UserFrom, { type: 'identities' }>['value'],
): IdentityHashCacheKey => {
  const sortedIdentities = identities.sort((a, b) => getIdentityKey(a).localeCompare(getIdentityKey(b)));

  return sortedIdentities.map(getIdentityKey).join('_');
};
// #endregion

export const createGetACEUser = ({
  configuration,
  monitoring,
}: {
  configuration: Configuration;
  monitoring: MonitoringContext;
}): {
  getACEUser: GetACEUser;
} => {
  const cachedUser = new TTLCache<IdentityHashCacheKey, { userId: string }>({
    ttl: configuration.userIdentity.cacheTTL,
    max: 1000,
  });

  return {
    getACEUser: async (userFrom): Promise<Result<{ userId: string }>> => {
      if (configuration.auth.type !== 'sema4-oidc-sso') {
        return {
          success: false,
          error: {
            code: 'invalid_auth_configuration',
            message: `Invalid auth configuration: Token validation only possible under 'sema4-oidc-sso' type, received: ${configuration.auth.type}`,
          },
        };
      }

      if (userFrom.type === 'aceUserId') {
        return {
          success: true,
          data: {
            userId: userFrom.value,
          },
        };
      }

      const userIdentityCacheKey = getIdentityHashCacheKey(userFrom.value);

      const userInCache = cachedUser.get(userIdentityCacheKey);

      if (userInCache) {
        return {
          success: true,
          data: {
            userId: userInCache.userId,
          },
        };
      }

      const targetUrl = joinUrl(configuration.auth.controlPlaneUrl, '/users');

      const userResult = await (async (): Promise<Result<ControlPlaneUserResponse>> => {
        try {
          const response = await fetch(targetUrl, {
            method: 'POST',
            headers: {
              'content-type': 'application/json',
            },
            body: JSON.stringify(userFrom.value),
          });

          if (!response.ok) {
            return {
              success: false,
              error: {
                code: 'auth_users_bad_response',
                message: `Received bad response for user verification: ${response.status} ${response.statusText}`,
              },
            };
          }

          const rawPayload = await response.json();
          const result = ControlPlaneUserResponse.safeParse(rawPayload);

          if (!result.success) {
            return {
              success: false,
              error: {
                code: 'auth_users_invalid_response',
                message: `Received bad response format for user authentication: ${formatZodError(result.error)}`,
              },
            };
          }

          return {
            success: true,
            data: result.data,
          };
        } catch (err) {
          monitoring.logger.error('Unexpected user authentication request error', {
            error: err as Error,
            requestMethod: 'POST',
            requestUrl: targetUrl,
          });

          return {
            success: false,
            error: {
              code: 'auth_users_request_error',
              message: 'Request for control-plane user authentication failed',
            },
          };
        }
      })();

      if (!userResult.success) {
        monitoring.logger.error('Unexpected user authentication error', {
          errorName: userResult.error.code,
          errorMessage: userResult.error.message,
        });

        return {
          success: false,
          error: {
            code: 'failed_retrieving_user_authentication_details',
            message: userResult.error.message,
          },
        };
      }

      const userId = userResult.data.userId;

      cachedUser.set(userIdentityCacheKey, { userId });

      return {
        success: true,
        data: {
          userId,
        },
      };
    },
  };
};

export const validateWorkRoomToken = async (
  {
    authManager,
    configuration,
    permissions,
  }: { authManager: AuthManager; configuration: Configuration; permissions: Array<Permission> },
  { encodedToken, tenantId }: { encodedToken: string; tenantId: string },
): Promise<
  Result<{
    userId: string;
    verifiedToken: string;
    capabilities: WorkroomUser['capabilities'];
  }>
> => {
  if (configuration.auth.type !== 'sema4-oidc-sso') {
    return {
      success: false,
      error: {
        code: 'invalid_auth_configuration',
        message: `Invalid auth configuration: Token validation only possible under 'sema4-oidc-sso' type, received: ${configuration.auth.type}`,
      },
    };
  }

  const verifier = getTokenVerifier({
    tokenInterface: SignInterface,
    getPublicKey: keyPairHelpers.getPublicKeyFromTrustedIssuer,
    trustedIssuers: configuration.auth.tokenIssuers,
  });

  const verifyTokenResult = await verifier.verify({
    token: encodedToken,
    expected: {
      type: 'WORK_ROOM_V1',
      scope: {
        type: 'WORK_ROOM_USER_V1',
        details: {
          userId: expectedValue.anyString,
          identities: [
            { value: expectedValue.anyString, type: 'sema4_sso' },
            { value: expectedValue.anyString, type: 'email' },
          ],
        },
      },
      capabilities: {
        byTenantId: {
          [tenantId]: permissions,
        },
      },
    },
  });

  if (!verifyTokenResult.isValid) {
    return {
      success: false,
      error: {
        code: 'invalid_token',
        message: verifyTokenResult.reason.message,
      },
    };
  }

  const aceUserResult = await authManager.resolveUserId({
    type: 'identities',
    value: verifyTokenResult.payload.scope.details.identities,
  });

  if (!aceUserResult.success) {
    return {
      success: false,
      error: aceUserResult.error,
    };
  }

  return {
    success: true,
    data: {
      userId: aceUserResult.data,
      verifiedToken: encodedToken,
      capabilities: verifyTokenResult.payload.capabilities,
    },
  };
};

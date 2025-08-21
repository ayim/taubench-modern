import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { NextFunction, Request, Response } from 'express';
import { extractGoogleUserIdentity, handleGoogleAuthCheck } from './google.js';
import { extractOIDCUserIdentity, handleOIDCAuthCheck } from './oidc.js';
import { extractSnowflakeUserIdentity, handleSnowflakeAuthCheck } from './snowflake.js';
import type { ACEUserId, GetACEUser, Permission } from '../../auth/oidc.js';
import type { Configuration } from '../../configuration.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { Result } from '../../utils/result.js';

export const createAuthMiddleware =
  ({
    authentication,
    configuration,
    getACEUser,
    monitoring,
  }: {
    authentication: 'with-permissions-check' | 'without-permissions-check';
    configuration: Configuration;
    getACEUser: GetACEUser;
    monitoring: MonitoringContext;
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
        return handleOIDCAuthCheck({ authentication, configuration, getACEUser, monitoring, next, req, res });

      default:
        exhaustiveCheck(configuration.auth);
    }
  };

export const extractAuthenticatedUserIdentity = async ({
  configuration,
  getACEUser,
  headers,
  monitoring,
  permissions,
}: {
  configuration: Configuration;
  getACEUser: GetACEUser;
  headers: Record<string, string>;
  monitoring: MonitoringContext;
  permissions: Array<Permission>;
}): Promise<
  Result<
    {
      userId: ACEUserId | string | null;
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
      return await extractOIDCUserIdentity({
        configuration,
        getACEUser,
        headers,
        monitoring,
        permissions,
      });

    default:
      exhaustiveCheck(configuration.auth);
  }
};

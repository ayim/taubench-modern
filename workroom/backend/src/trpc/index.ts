import { TRPCError } from '@trpc/server';
import type { ApiKeysManager } from '../apiKeys/index.js';
import type { ExpressRequest } from '../interfaces.js';
import { trpc, type RouterContext } from './trpc.js';
import type { AuthManager } from '../auth/AuthManager.js';
import type { Configuration } from '../configuration.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import * as apiKeysRoutes from './routes/apiKeys.js';
import * as configurationRoutes from './routes/configuration.js';
import { extractAuthenticatedUserIdentity } from '../middleware/auth/index.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/sessionManager.js';
import * as profileRoutes from './routes/profile.js';
import * as userManagementRoutes from './routes/userManagement.js';
import { extractHeadersFromRequest } from '../utils/request.js';

export const sparRouter = trpc.router({
  apiKeys: {
    ...apiKeysRoutes,
  },
  configuration: {
    ...configurationRoutes,
  },
  profile: {
    ...profileRoutes,
  },
  userManagement: {
    ...userManagementRoutes,
  },
});

export type SPARRouter = typeof sparRouter;

export const createRouterContext =
  ({
    apiKeysManager,
    authManager,
    configuration,
    database,
    monitoring,
    sessionManager,
  }: {
    apiKeysManager: ApiKeysManager | null;
    authManager: AuthManager;
    configuration: Configuration;
    database: DatabaseClient;
    monitoring: MonitoringContext;
    sessionManager: SessionManager;
  }) =>
  async ({ req }: { req: ExpressRequest }): Promise<RouterContext> => {
    const userIdentityResult = await extractAuthenticatedUserIdentity({
      authManager,
      configuration,
      headers: extractHeadersFromRequest(req.headers),
      monitoring,
      sessionManager,
    });
    if (!userIdentityResult.success) {
      monitoring.logger.error('TRPC authentication failed: Failed extracting user identity', {
        errorMessage: userIdentityResult.error.message,
        errorName: userIdentityResult.error.code,
        requestUrl: req.originalUrl,
      });

      // @TODO: We still get failed auth here when the access token expires, so we should
      // minutely-refactor the auth management a tad to support a more unified "auth refresh"
      // in TRPC as well as REST middleware.

      throw new TRPCError({
        code: 'UNAUTHORIZED',
        message: 'Invalid or missing authorization',
      });
    }

    const user: RouterContext['user'] = (() => {
      if (!userIdentityResult.data.userId || !userIdentityResult.data.userRole) {
        monitoring.logger.error('TRPC authentication failed: Incomplete user information', {
          requestUrl: req.originalUrl,
          userId: userIdentityResult.data.userId ?? '',
          userRole: userIdentityResult.data.userRole ?? '',
        });

        throw new TRPCError({
          code: 'UNAUTHORIZED',
          message: 'Invalid or missing authorization',
        });
      }

      return {
        id: userIdentityResult.data.userId,
        role: userIdentityResult.data.userRole,
      };
    })();

    return {
      apiKeysManager,
      authManager,
      authType: configuration.auth.type,
      database,
      monitoring,
      platform: {
        snowflakeEAIUrl: configuration.eaiLinkUrl,
      },
      req,
      sessionManager,
      user,
      tenantConfig: configuration.tenantConfig,
    };
  };

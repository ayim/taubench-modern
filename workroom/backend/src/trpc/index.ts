import { TRPCError } from '@trpc/server';
import type { ExpressRequest } from '../interfaces.js';
import { trpc, type RouterContext } from './trpc.js';
import type { AuthManager } from '../auth/AuthManager.js';
import type { Configuration } from '../configuration.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/sessionManager.js';
import * as profileRoutes from './routes/profile.js';
import * as userManagementRoutes from './routes/userManagement.js';
import { extractAuthenticatedUserIdentity } from '../middleware/auth/index.js';
import { extractHeadersFromRequest } from '../utils/request.js';

export const sparRouter = trpc.router({
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
    authManager,
    configuration,
    database,
    monitoring,
    sessionManager,
  }: {
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
      // Not needed for TRPC: we do permission checking at route definition,
      // which is outside of the agent server permissions definition anyway.
      permissions: [],
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

    const requiresUserIdentifier = configuration.auth.roleManagement;

    if (!userIdentityResult.data.userId || !userIdentityResult.data.userRole) {
      if (requiresUserIdentifier) {
        monitoring.logger.error('TRPC authentication failed: Incomplete user information', {
          requestUrl: req.originalUrl,
          userId: userIdentityResult.data.userId ?? '',
          userRole: userIdentityResult.data.userRole ?? '',
        });

        throw new TRPCError({
          code: 'UNAUTHORIZED',
          message: 'Invalid or missing authorization',
        });
      } else {
        // No user identification required for this auth setup, so simply mark
        // the current user as an administrator
        return {
          database,
          monitoring,
          sessionManager,
          user: {
            id: null,
            role: 'admin',
          },
        };
      }
    }

    return {
      database,
      monitoring,
      sessionManager,
      user: {
        id: userIdentityResult.data.userId,
        role: userIdentityResult.data.userRole,
      },
    };
  };

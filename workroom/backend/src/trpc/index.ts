import { TRPCError } from '@trpc/server';
import type { ExpressRequest } from '../interfaces.js';
import { trpc, type RouterContext } from './trpc.js';
import type { AuthManager } from '../auth/AuthManager.js';
import type { Configuration } from '../configuration.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/SessionManager.js';
import * as userManagementRoutes from './routes/userManagement.js';
import { extractAuthenticatedUserIdentity } from '../middleware/auth/index.js';
import { extractHeadersFromRequest } from '../utils/request.js';

export const sparRouter = trpc.router({
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
      });

      throw new TRPCError({
        code: 'UNAUTHORIZED',
        message: 'Invalid or missing authorization',
      });
    }

    if (!userIdentityResult.data.userId || !userIdentityResult.data.userRole) {
      monitoring.logger.error('TRPC authentication failed: Incomplete user information', {
        userId: userIdentityResult.data.userId ?? '',
        userRole: userIdentityResult.data.userRole ?? '',
      });

      throw new TRPCError({
        code: 'UNAUTHORIZED',
        message: 'Invalid or missing authorization',
      });
    }

    return {
      database,
      monitoring,
      user: {
        id: userIdentityResult.data.userId,
        role: userIdentityResult.data.userRole,
      },
    };
  };

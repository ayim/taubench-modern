import { initTRPC, TRPCError } from '@trpc/server';
import type { ApiKeysManager } from '../apiKeys/index.js';
import type { AuthManager } from '../auth/AuthManager.js';
import { Roles, type Permission } from '../auth/permissions.js';
import type { Configuration } from '../configuration.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { UserRole } from '../database/types/user.js';
import type { ExpressRequest, TenantConfig } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/sessionManager.js';

export type RouterContext = {
  apiKeysManager: ApiKeysManager | null;
  authManager: AuthManager;
  authType: Configuration['auth']['type'];
  database: DatabaseClient;
  monitoring: MonitoringContext;
  platform: {
    snowflakeEAIUrl: string | null;
  };
  req: ExpressRequest;
  sessionManager: SessionManager;
  user: Readonly<{
    id: string | null;
    role: UserRole;
  }>;
  tenantConfig: TenantConfig;
};

export const trpc = initTRPC.context<RouterContext>().create();

const errorLoggingMiddleware = trpc.middleware(async ({ ctx, path, next }) => {
  const result = await next();

  if (!result.ok) {
    ctx.monitoring.logger.error('TRPC error response', {
      errorName: result.error.code,
      errorMessage: result.error.message,
      requestUrl: path,
    });
  }

  return result;
});

export const authedProcedure = (requiredPermissions: Array<Permission>) =>
  trpc.procedure.use(errorLoggingMiddleware).use(async ({ ctx, next }) => {
    const userPermissions = Roles[ctx.user.role]?.permissions;
    if (
      !userPermissions ||
      !requiredPermissions.every((requiredPermission) => userPermissions.includes(requiredPermission))
    ) {
      throw new TRPCError({
        code: 'FORBIDDEN',
        message: 'User does not have permission to access this resource',
      });
    }

    return next();
  });

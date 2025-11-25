import { initTRPC, TRPCError } from '@trpc/server';
import { Roles, type Permission } from '../auth/permissions.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { UserRole } from '../database/types/user.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { SessionManager } from '../session/sessionManager.js';

export type RouterContext = {
  database: DatabaseClient;
  monitoring: MonitoringContext;
  sessionManager: SessionManager;
  user: Readonly<{
    id: string | null;
    role: UserRole;
  }>;
};

export const trpc = initTRPC.context<RouterContext>().create();

export const authedProcedure = (requiredPermissions: Array<Permission>) =>
  trpc.procedure.use(async ({ ctx, next }) => {
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

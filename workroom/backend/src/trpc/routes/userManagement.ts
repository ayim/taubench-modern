import { exhaustiveCheck, sequentialMap } from '@sema4ai/shared-utils';
import { TRPCError } from '@trpc/server';
import z from 'zod';
import { notAvailableForConfiguration } from './utils.js';
import { AllPermissions, RoleIDs, Roles, type Permission } from '../../auth/permissions.js';
import type { UpdateUserPayload } from '../../database/DatabaseClient.js';
import type { User, UserRole } from '../../database/types/user.js';
import { destroySessionsForUser } from '../../session/utils.js';
import { authedProcedure } from '../trpc.js';

export const listAvailablePermissions = authedProcedure(['users.read'])
  .output(
    z.object({
      permissions: z.array(z.custom<Permission>()),
    }),
  )
  .query(async () => ({
    permissions: [...AllPermissions],
  }));

export const listAvailableRoles = authedProcedure(['users.read'])
  .output(
    z.object({
      roles: z.array(
        z.object({
          id: z.custom<UserRole>((val) => RoleIDs.includes(val as UserRole)),
          name: z.string(),
        }),
      ),
    }),
  )
  .query(async () => {
    return {
      roles: [
        {
          id: Roles['admin'].id,
          name: Roles['admin'].name,
        },
        {
          id: Roles['knowledgeWorker'].id,
          name: Roles['knowledgeWorker'].name,
        },
      ],
    };
  });

export const getUserDetails = authedProcedure(['users.read'])
  .input(
    z.object({
      userId: z.uuid(),
    }),
  )
  .output(
    z.object({
      id: z.uuid(),
      firstName: z.string(),
      lastName: z.string(),
      role: z.custom<UserRole>((val) => RoleIDs.includes(val as UserRole)),
    }),
  )
  .query(async ({ ctx, input: { userId } }) => {
    const { database, monitoring } = ctx;

    const userResult = await database.getUser({ id: userId });
    if (!userResult.success) {
      monitoring.logger.error('Failed to retrieve users', {
        errorMessage: userResult.error.message,
        errorName: userResult.error.code,
      });

      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed retrieve user',
      });
    }

    return {
      id: userResult.data.id,
      firstName: userResult.data.first_name,
      lastName: userResult.data.last_name,
      role: userResult.data.role,
    };
  });

type AuthProviderIdentifier = z.infer<typeof AuthProviderIdentifier>;
const AuthProviderIdentifier = z.discriminatedUnion('type', [
  z.object({
    email: z.email().or(z.literal('')),
    type: z.literal('email'),
  }),
  z.object({
    id: z.string(),
    type: z.literal('id'),
  }),
]);

export const listUsers = authedProcedure(['users.read'])
  .output(
    z.object({
      providerIdentifierType: z.enum(['id', 'email']),
      users: z.array(
        z
          .object({
            id: z.string().uuid(),
            firstName: z.string(),
            lastName: z.string(),
            role: z.custom<UserRole>((val) => RoleIDs.includes(val as UserRole)),
            providerIdentifier: AuthProviderIdentifier,
          })
          .strict(),
      ),
    }),
  )
  .query(async ({ ctx }) => {
    const { authManager, authType, database, monitoring } = ctx;

    const usersResult = await database.getUsers();
    if (!usersResult.success) {
      monitoring.logger.error('Failed listing users', {
        errorMessage: usersResult.error.message,
        errorName: usersResult.error.code,
      });

      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed listing users',
      });
    }

    const authMetadataResult = authManager.getAuthorityMetadata();
    if (!authMetadataResult.success) {
      monitoring.logger.error('Failed retrieving authority metadata for service', {
        errorMessage: authMetadataResult.error.message,
        errorName: authMetadataResult.error.code,
      });

      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Invalid authentication configuration',
      });
    }

    const userIdentitiesResult = await database.getUsersIdentityValues({
      authority: authMetadataResult.data.authority,
      type: authMetadataResult.data.type,
    });
    if (!userIdentitiesResult.success) {
      monitoring.logger.error('Failed retrieving user identity values', {
        errorMessage: userIdentitiesResult.error.message,
        errorName: userIdentitiesResult.error.code,
      });

      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed listing users',
      });
    }

    const providerIdentifierType: 'id' | 'email' = (() => {
      switch (authType) {
        case 'snowflake':
          return 'id';

        case 'oidc':
          return 'email';

        case 'none':
          throw new TRPCError(notAvailableForConfiguration({ feature: 'User management' }));

        default:
          exhaustiveCheck(authType);
      }
    })();

    const resolveIdentifier = async (user: User): Promise<AuthProviderIdentifier> => {
      const targetIdentities = userIdentitiesResult.data[user.id] ?? [];

      if (targetIdentities.length === 0) {
        monitoring.logger.error('No identities found for user', {
          userId: user.id,
        });

        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Failed listing users',
        });
      }

      return providerIdentifierType === 'email'
        ? {
            email: targetIdentities[0].email ?? '',
            type: 'email',
          }
        : {
            id: targetIdentities[0].value,
            type: 'id',
          };
    };

    const users = await sequentialMap(
      usersResult.data.sort((a, b) => (a.first_name > b.first_name ? 1 : -1)),
      async (user) => ({
        id: user.id,
        firstName: user.first_name,
        lastName: user.last_name,
        role: user.role,
        providerIdentifier: await resolveIdentifier(user),
      }),
    );

    return {
      providerIdentifierType,
      users,
    };
  });

export const updateUser = authedProcedure(['users.write'])
  .input(
    z.object({
      update: z.object({
        role: z.custom<UserRole>((val) => RoleIDs.includes(val as UserRole)).optional(),
      }),
      userId: z.string().uuid(),
    }),
  )
  .mutation(async ({ ctx, input }) => {
    const { database, monitoring, sessionManager } = ctx;

    monitoring.logger.info('Update user', {
      userId: input.userId,
    });

    // Check user exists
    const existingUserResult = await database.getUser({ id: input.userId });
    if (!existingUserResult.success) {
      monitoring.logger.error('Failed to update user: No user found for ID', {
        userId: input.userId,
      });

      throw new TRPCError({
        code: 'NOT_FOUND',
        message: 'No user found for ID',
      });
    }

    const updatePayload: UpdateUserPayload = {
      id: input.userId,
    };

    if (input.update.role) {
      if (input.update.role !== 'admin') {
        // User is being demoted, so we need to ensure that they're not demoting themselves
        // while potentially being the LAST admin user..
        const currentAdminIdsResult = await database.getAdminUserIds();
        if (!currentAdminIdsResult.success) {
          monitoring.logger.error('Failed retrieving admin user IDs', {
            errorMessage: currentAdminIdsResult.error.message,
            errorName: currentAdminIdsResult.error.code,
            userId: input.userId,
          });

          throw new TRPCError({
            code: 'INTERNAL_SERVER_ERROR',
            message: 'Failed to update user role',
          });
        }

        if (currentAdminIdsResult.data.length === 1 && currentAdminIdsResult.data.includes(input.userId)) {
          // Target user is the only administrator
          monitoring.logger.error('User demotion failed: User is last administrator', {
            userId: input.userId,
          });

          throw new TRPCError({
            code: 'CONFLICT',
            message: 'At least one user must be admin: promote another user to admin before demoting yourself',
          });
        }
      }

      updatePayload.role = input.update.role;
    }

    const updateResult = await database.updateUser({
      user: updatePayload,
    });
    if (!updateResult.success) {
      monitoring.logger.error('Failed updating user', {
        errorMessage: updateResult.error.message,
        errorName: updateResult.error.code,
        userId: input.userId,
      });

      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed to update user',
      });
    }

    // Follow up: If a role was changed, kill any active sessions that user may have
    // to ensure that they get a clean environment.
    if (updatePayload.role) {
      const destroySessionsResult = await destroySessionsForUser({
        database,
        monitoring,
        sessionManager,
        userId: input.userId,
      });

      if (!destroySessionsResult.success) {
        monitoring.logger.error('Failed updating user', {
          errorMessage: destroySessionsResult.error.message,
          errorName: destroySessionsResult.error.code,
          userId: input.userId,
        });

        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Failed to clean up',
        });
      }
    }
  });

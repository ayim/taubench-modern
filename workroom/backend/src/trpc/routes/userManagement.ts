import { TRPCError } from '@trpc/server';
import z from 'zod';
import { RoleIDs, Roles } from '../../auth/permissions.js';
import type { UpdateUserPayload } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/users.js';
import { authedProcedure } from '../trpc.js';

export const listAvailableRoles = authedProcedure(['users.read'])
  .output(
    z.object({
      roles: z.array(
        z.object({
          id: z.custom<UserRole>((val) => RoleIDs.includes(val)),
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

export const listUsers = authedProcedure(['users.read'])
  .output(
    z.object({
      users: z.array(
        z
          .object({
            id: z.string().uuid(),
            firstName: z.string(),
            lastName: z.string(),
            role: z.custom<UserRole>((val) => RoleIDs.includes(val)),
          })
          .strict(),
      ),
    }),
  )
  .query(async ({ ctx }) => {
    const { database, monitoring } = ctx;

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

    return {
      users: usersResult.data
        .sort((a, b) => (a.first_name > b.first_name ? 1 : -1))
        .map((user) => ({
          id: user.id,
          firstName: user.first_name,
          lastName: user.last_name,
          role: user.role,
        })),
    };
  });

export const updateUser = authedProcedure(['users.write'])
  .input(
    z.object({
      update: z.object({
        role: z.custom<UserRole>((val) => RoleIDs.includes(val)).optional(),
      }),
      userId: z.string().uuid(),
    }),
  )
  .mutation(async ({ ctx, input }) => {
    const { database, monitoring } = ctx;

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
      updatePayload.role = input.update.role;
    }

    const updateResult = await database.updateUser({
      user: updatePayload,
    });
    if (!updateResult.success) {
      monitoring.logger.error('Failed updating user', {
        errorMessage: updateResult.error.message,
        errorName: updateResult.error.code,
      });

      throw new TRPCError({
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed to update user',
      });
    }
  });

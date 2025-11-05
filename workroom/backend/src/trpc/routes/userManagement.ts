import { TRPCError } from '@trpc/server';
import z from 'zod';
import { RoleNames } from '../../auth/permissions.js';
import type { UserRole } from '../../database/types/users.js';
import { authedProcedure } from '../trpc.js';

export const listUsers = authedProcedure([])
  .output(
    z.object({
      users: z.array(
        z
          .object({
            id: z.string().uuid(),
            firstName: z.string(),
            lastName: z.string(),
            role: z.custom<UserRole>((val) => RoleNames.includes(val)),
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
      users: usersResult.data.map((user) => ({
        id: user.id,
        firstName: user.first_name,
        lastName: user.last_name,
        role: user.role,
      })),
    };
  });

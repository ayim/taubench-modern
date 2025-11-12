import { TRPCError } from '@trpc/server';
import z from 'zod';
import { authedProcedure } from '../trpc.js';

export const getProfile = authedProcedure([])
  .output(
    z.object({
      user: z.object({
        firstName: z.string(),
        lastName: z.string(),
        profilePicture: z.string().nullable(),
      }),
    }),
  )
  .query(async ({ ctx }) => {
    const { database, monitoring, user } = ctx;

    if (user.id) {
      const userResult = await database.getUser({ id: user.id });
      if (!userResult.success) {
        monitoring.logger.error('Failed retrieve user', {
          errorMessage: userResult.error.message,
          errorName: userResult.error.code,
          userId: user.id,
        });

        throw new TRPCError({
          code: 'INTERNAL_SERVER_ERROR',
          message: 'Failed retrieve user',
        });
      }

      return {
        user: {
          firstName: userResult.data.first_name,
          lastName: userResult.data.last_name,
          profilePicture: userResult.data.profile_picture_url,
        },
      };
    }

    return {
      user: {
        firstName: 'User',
        lastName: '',
        profilePicture: null,
      },
    };
  });

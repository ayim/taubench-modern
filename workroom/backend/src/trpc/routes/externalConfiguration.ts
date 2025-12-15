import z from 'zod';
import { authedProcedure } from '../trpc.js';

export const getExternalConfigurationStatus = authedProcedure([])
  .output(
    z.object({
      snowflakeEAIUrl: z
        .url()
        .nullable()
        .describe('Optional URL for a remote page that provides EAI configuration information whilst on Snowflake.'),
    }),
  )
  .query(async ({ ctx }) => {
    const { platform } = ctx;

    return {
      snowflakeEAIUrl: platform.snowflakeEAIUrl,
    };
  });

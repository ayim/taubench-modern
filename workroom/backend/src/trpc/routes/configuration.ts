import z from 'zod';
import { TenantConfig } from '../../interfaces.js';
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

export const getTenantConfig = authedProcedure([])
  .output(TenantConfig)
  .query(async ({ ctx }) => {
    return ctx.tenantConfig;
  });

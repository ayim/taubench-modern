import { initTRPC } from '@trpc/server';
import type { OpenApiMeta } from 'trpc-to-openapi';
import { z } from 'zod';
import type { Configuration } from './configuration.ts';
import { DeploymentStatus, type DatabaseClient } from './lib/database.ts';
import { getDeploymentUrl, type createActionDeployer } from './lib/deployments.ts';

type ServerContext = {
  configuration: Configuration;
  db: DatabaseClient;
  runner: ReturnType<typeof createActionDeployer>;
};

const { procedure: publicProcedure, router } = initTRPC.meta<OpenApiMeta>().context<ServerContext>().create();

const GetDeploymentRequest = z.object({
  deploymentId: z.string(),
});
const GetDeploymentResponse = z
  .object({
    deploymentId: z.string(),
    status: DeploymentStatus,
    url: z.string().nullable(),
  })
  .nullable()
  .or(
    z.object({
      success: z.literal(false),
      error: z.object({
        code: z.string(),
        message: z.string(),
      }),
    }),
  );

type ListDeploymentsResponse = z.infer<typeof ListDeploymentsResponse>;
const ListDeploymentsResponse = z
  .array(
    z.object({
      deploymentId: z.string(),
      status: DeploymentStatus,
      url: z.string().nullable(),
    }),
  )
  .or(
    z.object({
      success: z.literal(false),
      error: z.object({
        code: z.string(),
        message: z.string(),
      }),
    }),
  );

const DeleteDeploymentRequest = z.object({
  deploymentId: z.string(),
});
const DeleteDeploymentResponse = z
  .object({
    deploymentId: z.string(),
    deleted: z.boolean(),
  })
  .nullable()
  .or(
    z.object({
      success: z.literal(false),
      error: z.object({
        code: z.string(),
        message: z.string(),
      }),
    }),
  );

export const appRouter = router({
  deployments: {
    get: publicProcedure
      .input(GetDeploymentRequest)
      .output(GetDeploymentResponse)
      .meta({
        openapi: {
          path: '/deployments/{deploymentId}',
          method: 'GET',
        },
      })
      .query(async ({ ctx, input: { deploymentId } }) => {
        const getDeploymentResult = await ctx.db.getDeployment({ id: deploymentId });
        if (!getDeploymentResult.success) {
          return getDeploymentResult;
        }
        const deployment = getDeploymentResult.data;
        if (deployment === null) {
          return null;
        }
        return {
          deploymentId: deployment.id,
          status: deployment.status,
          url: getDeploymentUrl({
            configuration: ctx.configuration,
            deploymentId: deployment.id,
          }),
        };
      }),
    list: publicProcedure
      .output(ListDeploymentsResponse)
      .meta({
        openapi: {
          path: '/deployments',
          method: 'GET',
        },
      })
      .query(async ({ ctx }) => {
        const listDeploymentsResult = await ctx.db.listDeployments();
        if (!listDeploymentsResult.success) {
          return listDeploymentsResult;
        }
        return listDeploymentsResult.data.map((deployment) => ({
          deploymentId: deployment.id,
          status: deployment.status,
          url: getDeploymentUrl({
            configuration: ctx.configuration,
            deploymentId: deployment.id,
          }),
        })) satisfies ListDeploymentsResponse;
      }),
    delete: publicProcedure
      .input(DeleteDeploymentRequest)
      .output(DeleteDeploymentResponse)
      .meta({
        openapi: {
          path: '/deployments/{deploymentId}',
          method: 'DELETE',
        },
      })
      .mutation(async ({ ctx, input: { deploymentId } }) => {
        const getDeploymentResult = await ctx.db.getDeployment({ id: deploymentId });
        if (!getDeploymentResult.success) {
          return getDeploymentResult;
        }
        const deployment = getDeploymentResult.data;
        if (deployment === null) {
          return {
            success: false,
            error: {
              code: 'deployment_not_found',
              message: `Deployment ${deploymentId} not found`,
            },
          };
        }

        const destroyDeploymentResult = await ctx.runner.destroyDeployment({ deploymentId: deployment.id });
        if (!destroyDeploymentResult.success) {
          return destroyDeploymentResult;
        }

        return {
          deploymentId: deployment.id,
          deleted: true,
        };
      }),
  },
});

export type AppRouter = typeof appRouter;

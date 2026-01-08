import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import type { Socket } from 'node:net';
import express from 'express';
import { createOpenApiExpressMiddleware } from 'trpc-to-openapi';
import z from 'zod';
import { getConfiguration } from './configuration.ts';
import { runMigrationsAndGetDatabaseClient } from './lib/database.ts';
import { createActionDeployer, getDeploymentUrl } from './lib/deployments.ts';
import { createDeploymentProxyMiddleware } from './lib/proxy.ts';
import { appRouter } from './router.ts';

const run = async () => {
  let applicationReady = false;

  const configuration = getConfiguration();

  await mkdir(join(configuration.persistentDataDirectory, 'sema4ai'), {
    recursive: true,
  });

  const app = express();

  app.get('/api/health', (_req, res) => {
    return res.status(200).json({
      status: 'ok',
    });
  });

  app.get('/api/ready', (_req, res) => {
    if (applicationReady) {
      return res.status(200).json({
        status: 'ok',
      });
    }
    return res.status(503).json({
      status: 'error',
      reason: 'action server rehydration in progress',
    });
  });

  console.log(`mcp-runtime listening on ${configuration.httpApiPort}`);
  const server = app.listen(configuration.httpApiPort);

  const db = await runMigrationsAndGetDatabaseClient(configuration);
  const runner = createActionDeployer({ configuration, db });
  await runner.rehydrateDeployments();

  app.post(
    '/api/deployments/:deploymentId',
    express.raw({
      type: 'application/octet-stream',
      limit: '50mb',
    }),
    async (req, res) => {
      if (!(req.body instanceof Buffer)) {
        throw new Error();
      }
      const buffer = req.body;

      const idParseResult = z.uuid().safeParse(req.params.deploymentId);
      if (!idParseResult.success) {
        return res.status(400).json({
          error: {
            code: 'invalid_deployment_id',
            message: `${req.params.deploymentId} is not a valid UUID`,
          },
        });
      }
      const deploymentId = idParseResult.data;

      try {
        const createDeploymentResult = await runner.createDeployment({
          deploymentId,
          agentPackageZip: buffer,
        });
        if (!createDeploymentResult.success) {
          return res.status(500).json(createDeploymentResult).send();
        }
        return res
          .status(200)
          .json({
            deploymentId: createDeploymentResult.data.id,
            status: createDeploymentResult.data.status,
            url: getDeploymentUrl({
              configuration,
              deploymentId: createDeploymentResult.data.id,
            }),
          })
          .send();
      } catch (error) {
        console.error(error);
        return res
          .status(500)
          .json({
            error: {
              code: 'failed_to_create_deployment',
              message: 'Failed to create deployment',
            },
          })
          .send();
      }
    },
  );

  app.use(
    '/api',
    createOpenApiExpressMiddleware({
      router: appRouter,
      createContext: ({ req }) => ({
        configuration,
        db,
        runner,
        req,
      }),
    }),
  );

  const deploymentProxyMiddleware = createDeploymentProxyMiddleware({ db });
  app.use('/deployments/:deploymentId', deploymentProxyMiddleware);

  applicationReady = true;

  const activeConnections = new Set<Socket>();

  server.on('connection', (connection) => {
    activeConnections.add(connection);
    connection.on('close', () => activeConnections.delete(connection));
  });

  const gracefulShutdown = (signal: 'SIGTERM' | 'SIGINT') => {
    console.log(`${signal} received, shutting down...`);

    server.close(async () => {
      console.log('HTTP server closed');
      await db.shutdown();
      process.exit(0);
    });

    setTimeout(() => {
      console.error(
        `Graceful shutdown timed out after ${configuration.gracefulShutdownTimeoutInSeconds} seconds, exiting`,
      );
      process.exit(1);
    }, configuration.gracefulShutdownTimeoutInSeconds * 1000);

    activeConnections.forEach((conn) => conn.destroy());
  };

  process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
  process.on('SIGINT', () => gracefulShutdown('SIGINT'));
};

run();

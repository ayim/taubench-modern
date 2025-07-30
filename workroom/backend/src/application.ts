import http from 'node:http';
import { resolve } from 'node:path';
import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import express, { type Application, type NextFunction, type Request, type Response } from 'express';
import createRouter from 'express-promise-router';
import type { Configuration } from './configuration.js';
import { createGetAgentMeta, createProxyToAgentServer } from './handlers/agents.js';
import { createHealthCheck } from './handlers/health.js';
import { createGetSparMeta, createGetSparTenantsList } from './handlers/meta.js';
import { createAssetServe, createIndexServe } from './handlers/static.js';
import { initializeWebSocketProxying } from './handlers/websocket.js';
import { createGetWorkroomMeta } from './handlers/workroom.js';
import { createAuthMiddleware } from './middleware/auth/index.js';
import { createRequestLogger } from './middleware/logging.js';
import type { MonitoringContext } from './monitoring/index.js';

export const createApplication = async ({
  configuration,
  monitoring,
}: {
  configuration: Configuration;
  monitoring: MonitoringContext;
}): Promise<{
  app: Application;
  start: () => Promise<void>;
  stop: () => Promise<void>;
}> => {
  monitoring.logger.info('Configuring application', {
    authMode: configuration.auth.type,
    deploymentType: configuration.deployment.type,
  });

  const app = express();
  const server = http.createServer(app);

  app.set('trust proxy', true);
  app.disable('x-powered-by');

  app.get('/healthz', createHealthCheck());
  app.get('/ready', createHealthCheck());

  const frontendAPIRouter = createRouter();
  app.use('/api', frontendAPIRouter);

  const makeFrontendMiddleware = () => [
    createRequestLogger({ monitoring }),
    createAuthMiddleware({ configuration, monitoring }),
  ];

  frontendAPIRouter.use(...makeFrontendMiddleware());

  if (configuration.deployment.type === 'ace') {
    const targetMetaPath = new URL(configuration.deployment.metaUrl).pathname;

    const baseURL = new URL(configuration.deployment.metaUrl);
    baseURL.pathname = '';

    app.get(
      '/meta',
      ...makeFrontendMiddleware(),
      createProxyToAgentServer({
        configuration,
        monitoring,
        rewriteAgentServerPath: () => targetMetaPath,
        targetBaseUrl: baseURL.toString(),
      }),
    );
  } else if (configuration.deployment.type === 'spcs') {
    const { handleWebsocketUpgrade } = initializeWebSocketProxying({
      configuration,
      monitoring,
      rewriteAgentServerPath: (currentPath) => currentPath,
      targetBaseUrl: configuration.deployment.agentRouterInternalUrl,
    });
    server.on('upgrade', handleWebsocketUpgrade);

    const targetMetaPath = new URL(configuration.deployment.metaUrl).pathname;

    const baseURL = new URL(configuration.deployment.metaUrl);
    baseURL.pathname = '';

    app.get(
      '/meta',
      ...makeFrontendMiddleware(),
      createProxyToAgentServer({
        configuration,
        monitoring,
        rewriteAgentServerPath: () => targetMetaPath,
        targetBaseUrl: baseURL.toString(),
      }),
    );

    app.all(
      '/backend/*',
      ...makeFrontendMiddleware(),
      createProxyToAgentServer({
        configuration,
        monitoring,
        // This is a NO-OP, but keeping it explicit on both ends is better
        // for maintainability and simplicity. We have more granular control
        // this way.
        rewriteAgentServerPath: (currentPath) => currentPath,
        targetBaseUrl: configuration.deployment.agentRouterInternalUrl,
      }),
    );
  } else if (configuration.deployment.type === 'spar') {
    const { handleWebsocketUpgrade } = initializeWebSocketProxying({
      configuration,
      monitoring,
      rewriteAgentServerPath: (current) => current.replace('/api/tenants/spar/agents', ''),
      targetBaseUrl: configuration.deployment.agentServerInternalUrl,
    });
    server.on('upgrade', handleWebsocketUpgrade);

    app.get('/meta', ...makeFrontendMiddleware(), createGetSparMeta({ configuration }));

    // @TODO: Remove this
    frontendAPIRouter.post(
      '/demo-create-agent',
      createProxyToAgentServer({
        configuration,
        monitoring,
        rewriteAgentServerPath: () => '/api/v2/agents/',
        targetBaseUrl: configuration.deployment.agentServerInternalUrl,
      }),
    );

    frontendAPIRouter.get('/tenants-list', createGetSparTenantsList());

    // Workroom routes
    frontendAPIRouter.get('/tenants/spar/workroom/meta', createGetWorkroomMeta());

    // Agent routes
    frontendAPIRouter.get('/tenants/spar/workroom/agents/:agentId/meta', createGetAgentMeta());
    frontendAPIRouter.all(
      '/tenants/spar/agents/api/v2/*',
      createProxyToAgentServer({
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace('/api/tenants/spar/agents', ''),
        targetBaseUrl: configuration.deployment.agentServerInternalUrl,
      }),
    );
    frontendAPIRouter.get(
      '/tenants/spar/workroom/agents/:agentId/details',
      createProxyToAgentServer({
        configuration,
        monitoring,
        rewriteAgentServerPath: (_current, getParam) => `/api/v2/agents/${getParam('agentId')}/agent-details`,
        targetBaseUrl: configuration.deployment.agentServerInternalUrl,
      }),
    );
  } else {
    exhaustiveCheck(configuration.deployment);
  }

  // Static routes / Frontend handling
  if (configuration.frontendMode === 'disk') {
    monitoring.logger.info('Frontend will be loaded from disk');

    app.use('/', createAssetServe({ root: resolve(import.meta.dirname, '../../frontend/dist') }));
    app.get('/*', createIndexServe({ root: resolve(import.meta.dirname, '../../frontend/dist') }));
  } else if (configuration.frontendMode === 'middleware') {
    monitoring.logger.info('Frontend will be processed using Vite middlewares');

    const viteDevServer = await import('vite').then((vite) =>
      vite.createServer({
        configFile: resolve(import.meta.dirname, '../../vite.config.ts'),
        server: { middlewareMode: true },
      }),
    );
    app.use(viteDevServer.middlewares);
  } else {
    exhaustiveCheck(configuration.frontendMode);
  }

  app.use((error: Error, req: Request, res: Response, _next: NextFunction) => {
    monitoring.logger.error('Request failed due to an internal error', {
      error,
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });

    res.status(500).send('Internal server error');
  });

  return {
    app,

    start: async () => {
      monitoring.logger.info('Starting server', {
        port: configuration.port,
      });

      await new Promise<void>((resolve) => {
        server.listen(configuration.port, () => {
          monitoring.logger.info('Server listening', {
            port: configuration.port,
          });

          resolve();
        });
      });
    },

    stop: async () => {
      await new Promise<void>((resolve, reject) => {
        server.close((err?: Error) => {
          if (err) {
            monitoring.logger.error('Server shutdown failed', {
              error: err,
            });

            return reject(err);
          }

          monitoring.logger.info('Server shutdown complete');

          resolve();
        });
      });
    },
  };
};

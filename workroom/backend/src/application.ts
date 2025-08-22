import http from 'node:http';
import { resolve } from 'node:path';
import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import cors from 'cors';
import express, { type Application, type NextFunction, type Request, type Response } from 'express';
import createRouter from 'express-promise-router';
import { createGetACEUser } from './auth/oidc.js';
import type { Configuration } from './configuration.js';
import { createGetAgentMeta, createProxyHandler } from './handlers/agents.js';
import { createHealthCheck } from './handlers/health.js';
import { createGetMeta, createGetSparTenantsList } from './handlers/meta.js';
import { createAssetServe, createIndexServe, initializeFrontendPlaceholders } from './handlers/static.js';
import { initializeWebSocketProxying } from './handlers/websocket.js';
import { createGetWorkroomMeta } from './handlers/workroom.js';
import { createAuthMiddleware } from './middleware/auth/index.js';
import { badPlatform } from './middleware/badRoute.js';
import { createRequestLogger } from './middleware/logging.js';
import { poweredByHeaders } from './middleware/poweredBy.js';
import { createTenantExtractionMiddleware } from './middleware/tenant.js';
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
    deploymentType: 'spar',
  });

  const { getACEUser } = createGetACEUser({
    configuration,
    monitoring,
  });

  const app = express();
  const server = http.createServer(app);

  app.set('trust proxy', 1);
  app.disable('x-powered-by');
  app.use(poweredByHeaders);
  // @TODO: Lock down CORS to public domain / explicit headers
  app.use(cors());

  app.get('/healthz', createHealthCheck());
  app.get('/ready', createHealthCheck());

  app.use(createRequestLogger({ monitoring }));

  const { handleWebsocketUpgrade } = initializeWebSocketProxying({
    configuration,
    getACEUser,
    monitoring,
    rewriteAgentServerPath: (current) => current.replace(/^\/tenants\/[^/]+\/agents/i, ''),
    targetBaseUrl: configuration.agentServerInternalUrl,
  });
  server.on('upgrade', (...eventArgs) =>
    handleWebsocketUpgrade(...eventArgs).catch((err) => {
      monitoring.logger.error('Websocket upgrade failed', {
        error: err as Error,
      });
    }),
  );

  const tenantRouter = createRouter({ mergeParams: true });
  app.use('/tenants/:tenantId', tenantRouter);

  tenantRouter.use(
    createTenantExtractionMiddleware({
      configuration,
      monitoring,
    }),
  );

  tenantRouter.get('/meta', createGetMeta({ configuration, monitoring }));

  tenantRouter.get(
    '/tenants-list',
    createAuthMiddleware({ authentication: 'without-permissions-check', configuration, getACEUser, monitoring }),
    createGetSparTenantsList({ configuration }),
  );

  tenantRouter.get(
    `/workroom/meta`,
    createAuthMiddleware({ authentication: 'without-permissions-check', configuration, getACEUser, monitoring }),
    createGetWorkroomMeta({ configuration }),
  );

  // Overrides
  if (configuration.legacyRoutingUrl) {
    monitoring.logger.info('Enabling legacy proxy routes', {
      requestUrl: configuration.legacyRoutingUrl,
    });

    tenantRouter.get(
      '/workroom/agents/:agentId/threads/:threadId/action-invocations/:actionInvocationId',
      createAuthMiddleware({ authentication: 'without-permissions-check', configuration, getACEUser, monitoring }),
      createProxyHandler({
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace(/^\//, '/backend/'),
        skipAuthentication: true, // Auth handled by agent-router
        targetBaseUrl: configuration.legacyRoutingUrl,
      }),
    );

    tenantRouter.get(
      '/workroom/agents/:agentId/me/oauth/permissions',
      createAuthMiddleware({ authentication: 'without-permissions-check', configuration, getACEUser, monitoring }),
      createProxyHandler({
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace(/^\//, '/backend/'),
        skipAuthentication: true, // Auth handled by agent-router
        targetBaseUrl: configuration.legacyRoutingUrl,
      }),
    );

    tenantRouter.get(
      '/workroom/oauth/authorize',
      createAuthMiddleware({ authentication: 'without-permissions-check', configuration, getACEUser, monitoring }),
      createProxyHandler({
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace(/^\//, '/backend/'),
        skipAuthentication: true, // Auth handled by agent-router
        targetBaseUrl: configuration.legacyRoutingUrl,
      }),
    );

    tenantRouter.delete(
      '/workroom/agents/:agentId/me/oauth/connections/:connectionId',
      createAuthMiddleware({ authentication: 'without-permissions-check', configuration, getACEUser, monitoring }),
      createProxyHandler({
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace(/^\//, '/backend/'),
        skipAuthentication: true, // Auth handled by agent-router
        targetBaseUrl: configuration.legacyRoutingUrl,
      }),
    );
  }

  // Agent server routes
  tenantRouter.get(
    '/workroom/agents/:agentId/meta',
    createAuthMiddleware({ authentication: 'without-permissions-check', configuration, getACEUser, monitoring }),
    createGetAgentMeta(),
  );
  tenantRouter.all(
    '/agents/api/v2/*',
    createAuthMiddleware({ authentication: 'with-permissions-check', configuration, getACEUser, monitoring }),
    createProxyHandler({
      configuration,
      monitoring,
      rewriteAgentServerPath: (current, getParam) => current.replace(`/tenants/${getParam('tenantId')}/agents`, ''),
      targetBaseUrl: configuration.agentServerInternalUrl,
    }),
  );
  tenantRouter.get(
    '/workroom/agents/:agentId/details',
    createAuthMiddleware({ authentication: 'with-permissions-check', configuration, getACEUser, monitoring }),
    createProxyHandler({
      configuration,
      monitoring,
      rewriteAgentServerPath: (_current, getParam) => `/api/v2/agents/${getParam('agentId')}/agent-details`,
      targetBaseUrl: configuration.agentServerInternalUrl,
    }),
  );

  // "Tombstoned" routes for ACE - these are overwritten by ACE's ingress
  // configuration, so they should work fine there but not be called in
  // other environments.
  tenantRouter.get('/workroom/meta', badPlatform);
  tenantRouter.post('/workroom/feedback', badPlatform);
  tenantRouter.get('/osb-resource-access', badPlatform);
  tenantRouter.get('/workroom/audit-logs', badPlatform);
  tenantRouter.use('/api/v1', badPlatform);

  // Index bounce
  app.get('/', (_req, res) => {
    res
      .set('x-sema4ai-redirect-source', 'spar-gateway')
      .redirect(302, `/tenants/${configuration.tenant.tenantId}/home`);
  });

  // Static routes / Frontend handling
  if (configuration.frontendMode === 'disk') {
    monitoring.logger.info('Frontend will be loaded from disk');

    const root = resolve(import.meta.dirname, '../../frontend/dist');

    await initializeFrontendPlaceholders({ configuration, root });

    tenantRouter.use('/', createAssetServe({ root }));
    tenantRouter.get('/*', createIndexServe({ root }));
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

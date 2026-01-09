import http from 'node:http';
import { resolve } from 'node:path';
import { createBasicKeyProvider, createSecretDataManager } from '@sema4ai/secret-management';
import { exhaustiveCheck } from '@sema4ai/shared-utils';
import * as trpcExpress from '@trpc/server/adapters/express';
import cors from 'cors';
import express, { type Application, type NextFunction, type Request, type Response } from 'express';
import createRouter from 'express-promise-router';
import rateLimit from 'express-rate-limit';
import type { AgentServerDatabaseClient } from './agentServerDatabaseMigration/AgentServerDatabaseClient.js';
import { createApiKeysManager } from './apiKeys/index.js';
import { AuthManager } from './auth/AuthManager.js';
import { autoPromoteUsersWithEmailsToAdmin } from './auth/utils/promotion.js';
import type { Configuration } from './configuration.js';
import type { DatabaseClient } from './database/DatabaseClient.js';
import { createFilesManager } from './files/filesManagement.js';
import { createGetAgentMeta, createProxyHandler } from './handlers/agents.js';
import { createAuthMetaHandler, createLogoutHandler } from './handlers/auth.js';
import { createConfigureDocumentIntelligence } from './handlers/documentIntelligence.js';
import { createFilesRouter } from './handlers/files.js';
import { createHealthCheck, createReadinessCheck } from './handlers/health.js';
import { createGetMeta, createGetSparTenantsList } from './handlers/meta.js';
import { createOIDCCallbackHandler } from './handlers/oidc.js';
import { createPublicApiSpecHandler } from './handlers/openapi.js';
import {
  createAssetServe,
  createCompressionMiddleware,
  createIndexServe,
  initializeFrontendPlaceholders,
} from './handlers/static.js';
import { initializeWebSocketProxying } from './handlers/websocket.js';
import { createGetWorkroomMeta } from './handlers/workroom.js';
import type { ErrorResponse } from './interfaces.js';
import {
  createApiKeyAuthMiddleware,
  createAuthMiddleware,
  createAuthRedirectMiddleware,
} from './middleware/auth/index.js';
import { createSnowflakeImplicitSessionMiddleware } from './middleware/auth/snowflake.js';
import { badPlatform } from './middleware/badRoute.js';
import { noCache } from './middleware/cache.js';
import { createRequestLogger } from './middleware/logging.js';
import { serverHeaders } from './middleware/server.js';
import { createTenantExtractionMiddleware } from './middleware/tenant.js';
import type { MonitoringContext } from './monitoring/index.js';
import { createSecretStorage } from './secretStorage/index.js';
import { createSessionMiddleware } from './session/middleware.js';
import { createSessionManager } from './session/sessionManager.js';
import { SESSION_COOKIES_NOT_ACTIVE } from './session/utils.js';
import { createRouterContext, sparRouter } from './trpc/index.js';
import { migrateAgentServerUsersForSPCS } from './utils/snowflake.js';

// TODO: Add 'rate_limit_exceeded' to ErrorResponse in @sema4ai/workroom-interface
type RateLimitErrorResponse = { error: { code: 'rate_limit_exceeded'; message: string } };

const AUTH_BYPASSED_PAGES = ['/tenants/:tenantId/logged-out'] as const;

export const createApplication = async ({
  agentServerDatabase,
  configuration,
  database,
  monitoring,
}: {
  agentServerDatabase: AgentServerDatabaseClient;
  configuration: Configuration;
  database: DatabaseClient;
  monitoring: MonitoringContext;
}): Promise<{
  appPublic: Application;
  appInternal: Application;
  start: () => Promise<void>;
  stop: () => Promise<void>;
}> => {
  monitoring.logger.info('Configuring application', {
    authMode: configuration.auth.type,
    logLevel: configuration.logLevel,
  });

  const secretDataManager = createSecretDataManager({
    masterKeyProvider: createBasicKeyProvider({
      identifier: 'spar-api-keys',
      masterPassword: configuration.secretManagement.secret,
    }),
    monitoring: {
      logger: {
        error: (errorMessage, errorDetails) => {
          monitoring.logger.error(errorMessage, {
            secretId: errorDetails?.secretId,
            error: errorDetails?.error,
          });
        },
      },
    },
    storage: createSecretStorage(database),
  });

  const authManager = new AuthManager({
    configuration,
    monitoring,
  });

  const initAuthResult = await authManager.initialize();
  if (!initAuthResult.success) {
    throw new Error(`Unexpected - failed initializing auth system: ${initAuthResult.error.message}`);
  }

  const filesManager =
    configuration.files.mode !== 'disabled' ? await createFilesManager({ configuration, monitoring }) : null;

  const sessionManager = createSessionManager({
    configuration,
    database,
    monitoring,
    secret: configuration.session?.secret ?? SESSION_COOKIES_NOT_ACTIVE,
  });

  if (configuration.auth.type === 'snowflake') {
    // Try to migrate existing users to new system
    await migrateAgentServerUsersForSPCS({
      agentServerDatabase,
      configuration,
      database,
      monitoring,
    });
  }

  await autoPromoteUsersWithEmailsToAdmin({
    database,
    emails: configuration.auth.autoPromoteEmails,
    monitoring,
    sessionManager,
  });

  const apiKeysManager = createApiKeysManager({
    database,
    monitoring,
    secretDataManager,
  });

  const appPublic = express();
  const serverPublic = http.createServer(appPublic);

  const appInternal = express();
  const serverInternal = http.createServer(appInternal);

  appPublic.set('trust proxy', 1);
  appPublic.disable('x-powered-by');
  appPublic.use(serverHeaders);
  appPublic.use(cors());
  appPublic.use(
    createSessionMiddleware({
      configuration,
      monitoring,
      sessionManager,
    }),
  );

  appInternal.disable('x-powered-by');
  appInternal.use(serverHeaders);

  appInternal.get('/healthz', createHealthCheck({ database, monitoring }));
  appInternal.get('/ready', createReadinessCheck());

  appPublic.use(createRequestLogger({ monitoring }));
  appInternal.use(createRequestLogger({ monitoring }));

  const { handleWebsocketUpgrade } = initializeWebSocketProxying({
    authManager,
    configuration,
    monitoring,
    rewriteAgentServerPath: (current) => current.replace(/^\/tenants\/[^/]+\/agents/i, ''),
    sessionManager,
    targetBaseUrl: configuration.agentServerInternalUrl,
  });
  serverPublic.on('upgrade', (...eventArgs) =>
    handleWebsocketUpgrade(...eventArgs).catch((err) => {
      monitoring.logger.error('Websocket upgrade failed', {
        error: err as Error,
      });
    }),
  );

  const tenantRouter = createRouter({ mergeParams: true });
  appPublic.use('/tenants/:tenantId', tenantRouter);

  tenantRouter.use(
    createTenantExtractionMiddleware({
      configuration,
      monitoring,
    }),
  );

  tenantRouter.use(
    createSnowflakeImplicitSessionMiddleware({
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
  );

  tenantRouter.get('/meta', noCache, createGetMeta({ configuration, monitoring }));

  tenantRouter.get(
    '/auth/meta',
    noCache,
    createAuthMetaHandler({
      configuration,
      monitoring,
      sessionManager,
    }),
  );
  tenantRouter.get(
    '/auth/logout',
    noCache,
    createLogoutHandler({
      authManager,
      configuration,
      monitoring,
      sessionManager,
    }),
  );

  tenantRouter.use(
    '/trpc',
    noCache,
    trpcExpress.createExpressMiddleware({
      router: sparRouter,
      createContext: createRouterContext({
        apiKeysManager,
        authManager,
        configuration,
        database,
        monitoring,
        sessionManager,
      }),
    }),
  );

  tenantRouter.get(
    '/tenants-list',
    noCache,
    createAuthMiddleware({
      authentication: 'without-permissions-check',
      authManager,
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
    createGetSparTenantsList({ configuration }),
  );

  tenantRouter.get(
    `/workroom/meta`,
    noCache,
    createAuthMiddleware({
      authentication: 'without-permissions-check',
      authManager,
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
    createGetWorkroomMeta({ configuration, monitoring }),
  );

  tenantRouter.get(
    '/workroom/oidc/callback',
    noCache,
    createOIDCCallbackHandler({ authManager, configuration, database, monitoring, sessionManager }),
  );

  // Overrides
  if (configuration.legacyRoutingUrl) {
    monitoring.logger.info('Enabling legacy proxy routes', {
      requestUrl: configuration.legacyRoutingUrl,
    });

    tenantRouter.get(
      '/workroom/agents/:agentId/threads/:threadId/action-invocations/:actionInvocationId',
      noCache,
      createAuthMiddleware({
        authentication: 'without-permissions-check',
        authManager,
        configuration,
        database,
        monitoring,
        sessionManager,
      }),
      createProxyHandler({
        apiType: 'private',
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace(/^\//, '/backend/'),
        skipAuthentication: true, // Auth handled by agent-router
        targetBaseUrl: configuration.legacyRoutingUrl,
      }),
    );

    tenantRouter.get(
      '/workroom/agents/:agentId/me/oauth/permissions',
      noCache,
      createAuthMiddleware({
        authentication: 'without-permissions-check',
        authManager,
        configuration,
        database,
        monitoring,
        sessionManager,
      }),
      createProxyHandler({
        apiType: 'private',
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace(/^\//, '/backend/'),
        skipAuthentication: true, // Auth handled by agent-router
        targetBaseUrl: configuration.legacyRoutingUrl,
      }),
    );

    tenantRouter.get(
      '/workroom/oauth/authorize',
      noCache,
      createAuthMiddleware({
        authentication: 'without-permissions-check',
        authManager,
        configuration,
        database,
        monitoring,
        sessionManager,
      }),
      createProxyHandler({
        apiType: 'private',
        configuration,
        monitoring,
        rewriteAgentServerPath: (current) => current.replace(/^\//, '/backend/'),
        skipAuthentication: true, // Auth handled by agent-router
        targetBaseUrl: configuration.legacyRoutingUrl,
      }),
    );

    tenantRouter.delete(
      '/workroom/agents/:agentId/me/oauth/connections/:connectionId',
      createAuthMiddleware({
        authentication: 'without-permissions-check',
        authManager,
        configuration,
        database,
        monitoring,
        sessionManager,
      }),
      createProxyHandler({
        apiType: 'private',
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
    noCache,
    createAuthMiddleware({
      authentication: 'without-permissions-check',
      authManager,
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
    createGetAgentMeta(),
  );
  tenantRouter.all(
    '/agents/api/v2/*',
    noCache,
    createAuthMiddleware({
      authentication: 'with-permissions-check',
      authManager,
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
    createProxyHandler({
      apiType: 'private',
      configuration,
      monitoring,
      rewriteAgentServerPath: (current, getParam) => current.replace(`/tenants/${getParam('tenantId')}/agents`, ''),
      targetBaseUrl: configuration.agentServerInternalUrl,
    }),
  );
  tenantRouter.get(
    '/workroom/agents/:agentId/details',
    noCache,
    createAuthMiddleware({
      authentication: 'with-permissions-check',
      authManager,
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
    createProxyHandler({
      apiType: 'private',
      configuration,
      monitoring,
      rewriteAgentServerPath: (_current, getParam) => `/api/v2/agents/${getParam('agentId')}/agent-details`,
      targetBaseUrl: configuration.agentServerInternalUrl,
    }),
  );

  // Document Intelligence routes
  tenantRouter.post(
    '/configure-document-intelligence',
    createAuthMiddleware({
      authentication: 'without-permissions-check',
      authManager,
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
    express.json(),
    createConfigureDocumentIntelligence({ configuration, monitoring }),
  );

  if (configuration.workroomMeta.features.publicAPI.enabled) {
    const publicApiRateLimiter = rateLimit({
      windowMs: configuration.publicApi.rateLimitWindowMs,
      limit: configuration.publicApi.rateLimit,
      standardHeaders: 'draft-8',
      handler: (_req, res) => {
        res.status(429).json({
          error: { code: 'rate_limit_exceeded', message: 'Too many requests, please try again later' },
        } satisfies RateLimitErrorResponse);
      },
    });

    tenantRouter.get('/api/v1', noCache, createPublicApiSpecHandler());

    tenantRouter.use(
      '/api/v1',
      publicApiRateLimiter,
      createApiKeyAuthMiddleware({ apiKeysManager, monitoring }),
      createProxyHandler({
        apiType: 'public',
        configuration,
        monitoring,
        rewriteAgentServerPath: (currentPath, getParam) =>
          currentPath.replace(`/tenants/${getParam('tenantId')}`, '').replace('/api/v1', '/api/public/v1'),
        targetBaseUrl: configuration.agentServerInternalUrl,
      }),
    );
  } else {
    tenantRouter.get('/api/v1', noCache, createPublicApiSpecHandler());
    tenantRouter.use('/api/v1/*', badPlatform);
  }

  // "Tombstoned" routes for ACE - these are overwritten by ACE's ingress
  // configuration, so they should work fine there but not be called in
  // other environments.
  tenantRouter.get('/workroom/meta', badPlatform);
  tenantRouter.post('/workroom/feedback', badPlatform);
  tenantRouter.get('/osb-resource-access', badPlatform);
  tenantRouter.get('/workroom/audit-logs', badPlatform);

  tenantRouter.use(
    createAuthRedirectMiddleware({
      authManager,
      bypassedPages: AUTH_BYPASSED_PAGES,
      configuration,
      database,
      monitoring,
      sessionManager,
    }),
  );

  // Index bounce
  appPublic.get('/', (_req, res) => {
    res
      .set('x-sema4ai-redirect-source', 'spar-gateway')
      .redirect(302, `/tenants/${configuration.tenant.tenantId}/home`);
  });

  appPublic.get('/oauth', (req, res) => {
    const tenantPrefix = `/tenants/${configuration.tenant.tenantId}`;
    res.set('x-sema4ai-redirect-source', 'spar-gateway').redirect(302, tenantPrefix + req.originalUrl);
  });

  appInternal.use('/files', noCache, createFilesRouter({ configuration, filesManager, monitoring }));

  // Static routes / Frontend handling
  if (configuration.frontendMode === 'disk') {
    monitoring.logger.info('Frontend will be loaded from disk');

    const root = resolve(import.meta.dirname, '../../frontend/dist');

    await initializeFrontendPlaceholders({ configuration, root });

    tenantRouter.use('/', createCompressionMiddleware({ root }), createAssetServe({ root }));
    tenantRouter.get('/*', createIndexServe({ root }));
  } else if (configuration.frontendMode === 'middleware') {
    monitoring.logger.info('Frontend will be processed using Vite middlewares');

    // Fixes static assets not resolved in dev mode
    const root = resolve(import.meta.dirname, '../../frontend/public');
    tenantRouter.use('/', createAssetServe({ root }));

    const viteDevServer = await import('vite').then((vite) =>
      vite.createServer({
        configFile: resolve(import.meta.dirname, '../../frontend/vite.config.ts'),
        server: {
          middlewareMode: true,
        },
      }),
    );
    appPublic.use(viteDevServer.middlewares);
  } else {
    exhaustiveCheck(configuration.frontendMode);
  }

  appPublic.use((error: Error, req: Request, res: Response, _next: NextFunction) => {
    monitoring.logger.error('Request failed due to an internal error', {
      error,
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });

    res
      .status(500)
      .json({ error: { code: 'internal_error', message: 'Internal server error' } } satisfies ErrorResponse);
  });

  return {
    appPublic,
    appInternal,

    start: async () => {
      monitoring.logger.info('Starting public server', {
        port: configuration.ports.public,
      });

      await new Promise<void>((resolve) => {
        serverPublic.listen(configuration.ports.public, () => {
          monitoring.logger.info('Public server listening', {
            port: configuration.ports.public,
          });

          resolve();
        });
      });

      monitoring.logger.info('Starting internal server', {
        port: configuration.ports.internal,
      });

      await new Promise<void>((resolve) => {
        serverInternal.listen(configuration.ports.internal, () => {
          monitoring.logger.info('Internal server listening', {
            port: configuration.ports.internal,
          });

          resolve();
        });
      });
    },

    stop: async () => {
      await new Promise<void>((resolve, reject) => {
        serverPublic.close((err?: Error) => {
          if (err) {
            monitoring.logger.error('Public server shutdown failed', {
              error: err,
            });

            return reject(err);
          }

          monitoring.logger.info('Public server shutdown complete');

          resolve();
        });
      });

      await new Promise<void>((resolve, reject) => {
        serverInternal.close((err?: Error) => {
          if (err) {
            monitoring.logger.error('Internal server shutdown failed', {
              error: err,
            });

            return reject(err);
          }

          monitoring.logger.info('Internal server shutdown complete');

          resolve();
        });
      });
    },
  };
};

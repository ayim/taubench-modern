import { randomUUID } from 'node:crypto';
import type { Cookie } from 'express-session';
import getPort from 'get-port';
import { http, HttpResponse } from 'msw';
import { setupServer, SetupServerApi } from 'msw/node';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { AgentServerDatabaseClient } from './agentServerDatabaseMigration/AgentServerDatabaseClient.js';
import { createApplication } from './application.js';
import type { Configuration } from './configuration.js';
import type { DatabaseClient } from './database/DatabaseClient.js';

const TEST_PRIVATE_KEY_BASE64 =
  'LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JR0hBZ0VBTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEJHMHdhd0lCQVFRZ2Y1TmZyRGNHejhwclpwS2QKYzZxWWJvUzhROUdxTkhNR3k4Z0JwZWxhMkFtaFJBTkNBQVNpWWI2alNydTltLzhLbXlzVjBuUFlaKzluR1p4YQoyRVVFZmFPWnQ1OXlBT1lta1JGZnlKVTNUcGVUSnRhRWpyalRFQUkyYkhRK2daN3p1SDlpaStXMQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg==';

const generateConfiguration = ({ agentServerInternalUrl }: { agentServerInternalUrl: string }): Configuration => ({
  agentServerInternalUrl,
  sparVersion: 'test',
  allowInsecureRequests: true,
  auth: {
    autoPromoteEmails: [],
    roleManagement: false,
    tokenIssuer: 'spar',
    type: 'none',
  },
  database: {
    agentServerSchema: 'v2',
    host: 'localhost',
    migrations: {
      lockTable: 'test-lock',
      recordsTable: 'test',
    },
    name: 'test',
    password: 'test',
    pool: {
      max: 1,
    },
    port: 5432,
    schema: 'test-schema',
    username: 'test',
  },
  dataServerCredentials: {
    credentials: {
      username: 'NOT_USED_IN_TESTS',
      password: 'NOT_USED_IN_TESTS',
    },
    api: {
      http: {
        url: 'NOT_USED_IN_TESTS',
        port: 'NOT_USED_IN_TESTS' as unknown as number,
      },
      mysql: {
        host: 'NOT_USED_IN_TESTS',
        port: 'NOT_USED_IN_TESTS' as unknown as number,
      },
    },
  },
  eaiLinkUrl: null,
  featuresUrl: null,
  files: {
    mode: 'disabled',
  },
  frontendMode: 'disk',
  legacyRoutingUrl: null,
  logLevel: 'INFO',
  metaUrl: null,
  ports: {
    internal: 'NOT_USED_IN_TESTS' as unknown as number,
    public: 'NOT_USED_IN_TESTS' as unknown as number,
  },
  publicApi: {
    rateLimit: 'NOT_USED_IN_TESTS' as unknown as number,
    rateLimitWindowMs: 'NOT_USED_IN_TESTS' as unknown as number,
  },
  secretManagement: {
    secret: 'NOT_USED_IN_TESTS',
  },
  session: null,
  sessionCookieMaxAgeMs: 60 * 60 * 1000,
  tenant: {
    tenantId: 'spar-test',
    tenantName: 'SPAR test',
  },
  userIdentity: {
    cacheTTL: 300,
  },
  workroomMeta: {
    features: {
      agentAuthoring: {
        enabled: true,
        reason: null,
      },
      agentConfiguration: {
        enabled: true,
        reason: null,
      },
      agentDetails: {
        enabled: true,
        reason: null,
      },
      agentEvals: {
        enabled: true,
        reason: null,
      },
      deploymentWizard: {
        enabled: true,
        reason: null,
      },
      developerMode: {
        enabled: true,
        reason: null,
      },
      documentIntelligence: {
        enabled: true,
        reason: null,
      },
      mcpServersManagement: {
        enabled: true,
        reason: null,
      },
      publicAPI: {
        enabled: false,
        reason: null,
      },
      semanticDataModels: {
        enabled: true,
        reason: null,
      },
      settings: {
        enabled: true,
        reason: null,
      },
      userManagement: {
        enabled: true,
        reason: null,
      },
      workerAgents: {
        enabled: true,
        reason: null,
      },
    },
  },
});

const getMockAgentServerDatabase = (): AgentServerDatabaseClient => {
  return {
    getAllUsers: () =>
      Promise.resolve({
        success: true,
        data: [],
      } satisfies Awaited<ReturnType<AgentServerDatabaseClient['getAllUsers']>>),
    setUserSub: () =>
      Promise.resolve({
        success: true,
        data: undefined,
      } satisfies Awaited<ReturnType<AgentServerDatabaseClient['setUserSub']>>),
    userTableMigratedAndReady: () =>
      Promise.resolve({
        success: true,
        data: true,
      }),
  } as unknown as AgentServerDatabaseClient;
};

const getMockDatabase = (): DatabaseClient => {
  return {
    findUserIdentities: () =>
      Promise.resolve({
        success: true,
        data: [],
      } satisfies Awaited<ReturnType<DatabaseClient['findUserIdentities']>>),
    getUserIds: () =>
      Promise.resolve({
        success: true,
        data: [],
      } satisfies Awaited<ReturnType<DatabaseClient['getUserIds']>>),
  } as unknown as DatabaseClient;
};

describe('application', () => {
  const USER_ID = randomUUID();

  let service: Awaited<ReturnType<typeof createApplication>>;
  let mockServer: SetupServerApi | null = null;

  afterEach(async () => {
    if (mockServer) {
      mockServer.close();
      mockServer = null;
    }
  });

  describe('(no auth, no meta)', () => {
    const THREADS = [
      {
        user_id: USER_ID,
        agent_id: 'ee405d56-c37e-4030-89b6-d4839e2678a9',
        name: 'Chat 1',
        thread_id: '66d60f4d-0a06-4644-b257-7d7a036edd05',
        messages: [],
        created_at: '2025-07-28T16:36:35.333023Z',
        updated_at: '2025-07-28T16:36:35.333024Z',
        metadata: {},
      },
    ];

    beforeEach(async () => {
      const targetPort = await getPort();
      const targetServerUrl = `http://127.0.0.1:${targetPort}`;

      mockServer = setupServer(
        http.get(`${targetServerUrl}/api/v2/threads`, () => {
          return HttpResponse.json(THREADS);
        }),
      );

      mockServer.listen({
        onUnhandledRequest: () => {
          // Squelch
        },
      });

      service = await createApplication({
        agentServerDatabase: getMockAgentServerDatabase(),
        configuration: generateConfiguration({ agentServerInternalUrl: targetServerUrl }),
        database: getMockDatabase(),
        monitoring: {
          logger: {
            debug: () => {},
            info: () => {},
            error: () => {},
          },
        },
      });
    });

    it('returns expected meta', async () => {
      await request(service.appPublic).get('/tenants/spar-test/meta').expect(200).expect({
        deploymentType: 'spar',
        version: 'test',
        workroomTenantListUrl: '/tenants/spar-test/tenants-list',
      });
    });

    it('returns expected proxied threads', async () => {
      await request(service.appPublic).get('/tenants/spar-test/agents/api/v2/threads').expect(200).expect(THREADS);
    });

    it('redirects / to tenant-prefixed URL', async () => {
      await request(service.appPublic).get('/').expect(302).expect('location', '/tenants/spar-test/home');
    });
  });

  describe('(snowflake auth)', () => {
    beforeEach(async () => {
      service = await createApplication({
        agentServerDatabase: getMockAgentServerDatabase(),
        configuration: {
          ...generateConfiguration({ agentServerInternalUrl: '' }),
          auth: {
            autoPromoteEmails: [],
            roleManagement: false,
            jwtPrivateKeyB64: TEST_PRIVATE_KEY_BASE64,
            tokenIssuer: 'spar',
            type: 'snowflake',
          },
        },
        database: {
          ...getMockDatabase(),
          findActiveSession: () =>
            Promise.resolve({
              success: true,
              data: {
                id: randomUUID(),
                data: {
                  cookie: {} as unknown as Cookie,
                  auth: {
                    stage: 'authenticated',
                    userId: randomUUID(),
                    userRole: 'admin',
                  },
                  authType: 'snowflake',
                },
                expires: new Date(),
                created_at: new Date(),
                updated_at: new Date(),
              },
            } satisfies Awaited<ReturnType<DatabaseClient['findActiveSession']>>),
        } as unknown as DatabaseClient,
        monitoring: {
          logger: {
            debug: () => {},
            info: () => {},
            error: () => {},
          },
        },
      });
    });

    it('fails for missing authentication', async () => {
      await request(service.appPublic).get('/tenants/spar-test/tenants-list').expect(401);
    });

    it('succeeds for valid authentication', async () => {
      const response = await request(service.appPublic)
        .get('/tenants/spar-test/tenants-list')
        .set('sf-context-current-user', 'test@sema4.ai')
        .expect(200);

      expect(response.body.data).toHaveLength(1);
      expect(response.body.data[0]).toHaveProperty('id', 'spar-test');
    });
  });
});

import { randomUUID } from 'node:crypto';
import type { Cookie } from 'express-session';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createApplication } from './application.js';
import type { Configuration } from './configuration.js';
import type { DatabaseClient } from './database/DatabaseClient.js';

const generateConfiguration = ({ agentServerInternalUrl }: { agentServerInternalUrl: string }): Configuration => ({
  agentServerInternalUrl,
  sparVersion: 'test',
  allowInsecureRequests: true,
  auth: {
    autoPromoteEmails: [],
    tokenIssuer: 'spar',
    type: 'snowflake',
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
  eaiLinkUrl: null,
  files: {
    mode: 'disabled',
  },
  frontendMode: 'disk',
  logLevel: 'INFO',
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
  tenantConfig: {
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

const mockMonitoring = {
  logger: {
    debug: () => {},
    info: () => {},
    error: () => {},
  },
};

describe('application', () => {
  let service: Awaited<ReturnType<typeof createApplication>>;

  afterEach(async () => {});

  describe('(snowflake auth)', () => {
    beforeEach(async () => {
      service = await createApplication({
        configuration: generateConfiguration({ agentServerInternalUrl: '' }),
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
        monitoring: mockMonitoring,
      });
    });

    it('redirects / to tenant-prefixed URL', async () => {
      await request(service.appPublic).get('/').expect(302).expect('location', '/tenants/spar-test/home');
    });

    it('returns expected meta', async () => {
      await request(service.appPublic).get('/tenants/spar-test/meta').expect(200).expect({
        // deploymentType is required for client-side authentication (getWorkroomToken). Remove once getWorkroomToken no longer depends on it.
        deploymentType: 'spar',
        version: 'test',
        workroomTenantListUrl: '/tenants/spar-test/tenants-list',
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

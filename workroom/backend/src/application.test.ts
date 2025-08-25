import { randomUUID } from 'node:crypto';
import getPort from 'get-port';
import { http, HttpResponse } from 'msw';
import { setupServer, SetupServerApi } from 'msw/node';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createApplication } from './application.js';
import type { Configuration } from './configuration.js';

const TEST_PRIVATE_KEY_BASE64 =
  'LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JR0hBZ0VBTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEJHMHdhd0lCQVFRZ2Y1TmZyRGNHejhwclpwS2QKYzZxWWJvUzhROUdxTkhNR3k4Z0JwZWxhMkFtaFJBTkNBQVNpWWI2alNydTltLzhLbXlzVjBuUFlaKzluR1p4YQoyRVVFZmFPWnQ1OXlBT1lta1JGZnlKVTNUcGVUSnRhRWpyalRFQUkyYkhRK2daN3p1SDlpaStXMQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg==';

const generateConfiguration = ({ agentServerInternalUrl }: { agentServerInternalUrl: string }): Configuration => ({
  agentServerInternalUrl,
  auth: {
    tokenIssuer: 'spar',
    type: 'none',
  },
  frontendMode: 'disk',
  legacyRoutingUrl: null,
  metaUrl: null,
  tenant: {
    tenantId: 'spar-test',
    tenantName: 'SPAR test',
  },
  port: 8001, // not used
  userIdentity: {
    cacheTTL: 300,
  },
  controlPlaneUrl: null,
  dataServer: {
    mode: 'disabled',
  },
});

describe('application', () => {
  const ACE_ID = randomUUID();
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
        configuration: generateConfiguration({ agentServerInternalUrl: targetServerUrl }),
        monitoring: {
          logger: {
            info: () => {},
            error: () => {},
          },
        },
      });
    });

    it('returns expected meta', async () => {
      await request(service.app).get('/tenants/spar-test/meta').expect(200).expect({
        deploymentType: 'spar',
        workroomTenantListUrl: '/tenants/spar-test/tenants-list',
      });
    });

    it('returns expected proxied threads', async () => {
      await request(service.app).get('/tenants/spar-test/agents/api/v2/threads').expect(200).expect(THREADS);
    });

    it('redirects / to tenant-prefixed URL', async () => {
      await request(service.app).get('/').expect(302).expect('location', '/tenants/spar-test/home');
    });
  });

  describe('(snowflake auth)', () => {
    beforeEach(async () => {
      service = await createApplication({
        configuration: {
          ...generateConfiguration({ agentServerInternalUrl: '' }),
          auth: {
            jwtPrivateKeyB64: TEST_PRIVATE_KEY_BASE64,
            tokenIssuer: 'spar',
            type: 'snowflake',
          },
        },
        monitoring: {
          logger: {
            info: () => {},
            error: () => {},
          },
        },
      });
    });

    it('fails for missing authentication', async () => {
      await request(service.app).get('/tenants/spar-test/tenants-list').expect(401);
    });

    it('succeeds for valid authentication', async () => {
      const response = await request(service.app)
        .get('/tenants/spar-test/tenants-list')
        .set('sf-context-current-user', 'test@sema4.ai')
        .expect(200);

      expect(response.body.data).toHaveLength(1);
      expect(response.body.data[0]).toHaveProperty('id', 'spar-test');
    });
  });

  describe('(oidc auth, meta pass-through)', () => {
    beforeEach(async () => {
      const targetPort = await getPort();
      const targetServerUrl = `http://127.0.0.1:${targetPort}`;

      mockServer = setupServer(
        http.get(`${targetServerUrl}/meta`, ({ request }) => {
          expect(request.headers.get('x-sema4ai-test-header')).toEqual('test value');

          return HttpResponse.json({
            aceId: ACE_ID,
            instanceId: 'dev2',
          });
        }),
      );

      mockServer.listen({
        onUnhandledRequest: () => {
          // Squelch
        },
      });

      service = await createApplication({
        configuration: {
          ...generateConfiguration({ agentServerInternalUrl: targetServerUrl }),
          auth: {
            controlPlaneUrl: targetServerUrl,
            jwtPrivateKeyB64: TEST_PRIVATE_KEY_BASE64,
            tokenIssuer: 'ace',
            tokenIssuers: [],
            type: 'sema4-oidc-sso',
          },
          metaUrl: `${targetServerUrl}/meta`,
          tenant: {
            tenantId: 'ace-test',
            tenantName: 'ACE test',
          },
        },
        monitoring: {
          logger: {
            info: () => {},
            error: () => {},
          },
        },
      });
    });

    it('returns 404 for old meta', async () => {
      await request(service.app).get('/meta').expect(404);
    });

    it('returns expected meta via proxy', async () => {
      await request(service.app)
        .get('/tenants/ace-test/meta')
        .set('x-sema4ai-test-header', 'test value')
        .expect(200)
        .expect({
          aceId: ACE_ID,
          instanceId: 'dev2',
        });
    });

    it('fails for missing authentication', async () => {
      await request(service.app).get('/tenants/ace-test/tenants-list').expect(401);
    });

    it('fails for invalid authentication', async () => {
      await request(service.app)
        .get('/tenants/ace-test/tenants-list')
        .set('Authorization', 'Bearer abc123')
        .expect(403);
    });
  });
});

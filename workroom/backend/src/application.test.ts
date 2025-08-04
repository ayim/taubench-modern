import getPort from 'get-port';
import { http, HttpResponse } from 'msw';
import { setupServer, SetupServerApi } from 'msw/node';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createApplication } from './application.js';

const ACE_ID = 'f5f1ee60-6270-4372-859f-3bd430d1312b';

describe('application', () => {
  let service: Awaited<ReturnType<typeof createApplication>>;
  let mockServer: SetupServerApi | null = null;

  afterEach(async () => {
    if (mockServer) {
      mockServer.close();
      mockServer = null;
    }
  });

  describe('in spar mode', () => {
    const THREADS = [
      {
        user_id: 'b623f27c-d91e-4249-a5c7-4290dcc435e3',
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
        configuration: {
          auth: {
            type: 'none',
          },
          deployment: {
            agentServerInternalUrl: targetServerUrl,
            type: 'spar',
          },
          frontendMode: 'disk',
          legacyRoutingUrl: null,
          tenant: {
            tenantId: 'spar-test',
            tenantName: 'SPAR test',
            type: 'static',
          },
          port: 8001, // not used
        },
        monitoring: {
          logger: {
            info: () => {},
            error: () => {},
          },
        },
      });
    });

    it('returns expected /meta', async () => {
      await request(service.app).get('/meta').expect(200).expect({
        deploymentType: 'spar',
        workroomTenantListUrl: '/api/tenants-list',
      });
    });

    it('returns expected proxied threads', async () => {
      await request(service.app).get('/api/tenants/spar-test/agents/api/v2/threads').expect(200).expect(THREADS);
    });
  });

  describe('in ACE mode', () => {
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
          auth: {
            type: 'none',
          },
          deployment: {
            metaUrl: `${targetServerUrl}/meta`,
            type: 'ace',
          },
          frontendMode: 'disk',
          legacyRoutingUrl: null,
          tenant: {
            tenantId: 'ace-test',
            tenantName: 'ACE test',
            type: 'static',
          },
          port: 8001, // not used
        },
        monitoring: {
          logger: {
            info: () => {},
            error: () => {},
          },
        },
      });
    });

    it('returns expected /meta via proxy', async () => {
      await request(service.app).get('/meta').set('x-sema4ai-test-header', 'test value').expect(200).expect({
        aceId: ACE_ID,
        instanceId: 'dev2',
      });
    });
  });
});

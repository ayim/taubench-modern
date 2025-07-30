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
    beforeEach(async () => {
      const targetServerUrl = '';

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

  describe('in SPCS mode', () => {
    beforeEach(async () => {
      const targetPort = await getPort();
      const targetServerUrl = `http://127.0.0.1:${targetPort}`;

      mockServer = setupServer(
        http.get(`${targetServerUrl}/meta`, ({ request }) => {
          expect(request.headers.get('x-sema4ai-test-header')).toEqual('test value spcs');

          return HttpResponse.json({
            deploymentType: 'spcs',
            workroomTenantListUrl: '/backend/workspaces',
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
            agentRouterInternalUrl: targetServerUrl,
            metaUrl: `${targetServerUrl}/meta`,
            type: 'spcs',
          },
          frontendMode: 'disk',
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
      await request(service.app).get('/meta').set('x-sema4ai-test-header', 'test value spcs').expect(200).expect({
        deploymentType: 'spcs',
        workroomTenantListUrl: '/backend/workspaces',
      });
    });
  });
});

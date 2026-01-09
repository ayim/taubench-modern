import type { Request, Response } from 'express';
import type { Configuration } from '../configuration.js';
import { createProxyHandler } from './agents.js';
import type { MonitoringContext } from '../monitoring/index.js';

export const createGetMeta =
  ({ configuration, monitoring }: { configuration: Configuration; monitoring: MonitoringContext }) =>
  (req: Request, res: Response) => {
    if (configuration.metaUrl) {
      const targetMetaPath = new URL(configuration.metaUrl).pathname;

      const baseURL = new URL(configuration.metaUrl);
      baseURL.pathname = '';

      return createProxyHandler({
        apiType: 'private',
        configuration,
        monitoring,
        rewriteAgentServerPath: () => targetMetaPath,
        skipAuthentication: true,
        targetBaseUrl: baseURL.toString(),
      })(req, res);
    }

    const meta: Record<string, string> = {
      deploymentType: 'spar',
      version: configuration.sparVersion,
      workroomTenantListUrl: `/tenants/${configuration.tenant.tenantId}/tenants-list`,
    };

    if (configuration.session) {
      meta.auth = 'session';
    }

    res.json(meta);
  };

export const createGetSparTenantsList =
  ({ configuration }: { configuration: Configuration }) =>
  (_req: Request, res: Response) => {
    res.json({
      data: [
        {
          id: configuration.tenant.tenantId,
          name: configuration.tenant.tenantName,
          organization: {
            id: 'spar_org_id_not_used',
            name: 'spar_org_name_not_used',
          },
          environment: {
            id: 'spar_environment_id_not_used',
            url: '/',
          },
        },
      ],
    });
  };

import type { Request, Response } from 'express';
import type { Configuration } from '../configuration.js';

export const createGetMeta =
  ({ configuration }: { configuration: Configuration }) =>
  (_req: Request, res: Response) => {
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

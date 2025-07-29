import type { Request, Response } from 'express';
import type { Configuration } from '../configuration.js';

export const createGetSparMeta =
  ({ configuration }: { configuration: Configuration }) =>
  (_req: Request, res: Response) => {
    res.json({
      deploymentType: configuration.deployment.type,
      workroomTenantListUrl: '/api/tenants-list',
    });
  };

export const createGetSparTenantsList = () => (_req: Request, res: Response) => {
  res.json({
    data: [
      {
        id: 'spar',
        name: 'SPAR DEV',
        organization: {
          id: 'spar_org_id',
          name: 'SPAR DEV ORG',
        },
        environment: {
          id: '_NOT_USED_IN_SPAR_',
          url: '/api',
        },
      },
    ],
  });
};

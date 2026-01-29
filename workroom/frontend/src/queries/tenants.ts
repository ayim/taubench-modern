import { useQuery } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';
import { createSparQueryOptions } from './shared';

const getListUserTenantsQueryKey = () => ['tenants'];
const getGetUserTenantsQueryKey = (tenantId: string) => ['tenants', tenantId];

export interface UserTenant {
  id: string;
  name: string;
  organization: {
    id: string;
    name: string;
  };
  environment: {
    id: string;
    url: string;
    workroom_url?: string; // only present on ACE
    tenant_workroom_url?: string | null; // only present on ACE >=1.5.0
  };
}

export const listUserTenantsQueryOptions = createSparQueryOptions()(({ agentAPIClient }) => ({
  queryKey: getListUserTenantsQueryKey(),
  queryFn: async (): Promise<UserTenant[]> => {
    const response = await agentAPIClient.getTenants();
    return response;
  },
}));

export const useListUserTenantsQuery = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  return useQuery(listUserTenantsQueryOptions({ agentAPIClient }));
};

export const getUserTenantQueryOptions = createSparQueryOptions<{ tenantId: string }>()(
  ({ agentAPIClient, tenantId }) => ({
    queryKey: getGetUserTenantsQueryKey(tenantId),
    queryFn: async (): Promise<UserTenant | undefined> => {
      const response = await agentAPIClient.getTenants();
      return response.find((curr) => curr.id === tenantId);
    },
  }),
);

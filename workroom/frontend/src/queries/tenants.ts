import { queryOptions, useQuery } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';
import { QueryProps } from './shared';

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
  };
}

export const listUserTenantsQueryOptions = ({ agentAPIClient }: QueryProps) =>
  queryOptions({
    queryKey: getListUserTenantsQueryKey(),
    queryFn: async (): Promise<UserTenant[]> => {
      const response = await agentAPIClient.getTenants();
      return response;
    },
  });

export const useListUserTenantsQuery = () => {
  const { agentAPIClient } = useRouteContext({ from: '/$tenantId' });
  return useQuery(listUserTenantsQueryOptions({ agentAPIClient }));
};

export const getUserTenantQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: getGetUserTenantsQueryKey(tenantId),
    queryFn: async (): Promise<UserTenant | undefined> => {
      const response = await agentAPIClient.getTenants();
      return response.find((curr) => curr.id === tenantId);
    },
  });

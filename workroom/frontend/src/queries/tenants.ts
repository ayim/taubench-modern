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
  };
}

export const listUserTenantsQueryOptions = ({ agentAPIClient }: QueryProps) =>
  queryOptions({
    queryKey: getListUserTenantsQueryKey(),
    queryFn: async (): Promise<UserTenant[]> => {
      const response = await agentAPIClient.getTenants();

      const currentLocationHostname = window.location.hostname;
      // the hostname is an ace url when we visit workroom using the ace endpoint
      // if it is not an ace url, it is the main work room URL (tied to the organisation) that allows to access all workspaces across all ACEs
      const isAceUrl = currentLocationHostname.startsWith('ace-');

      if (isAceUrl) {
        return response.filter((tenant) => {
          return tenant.environment.url.includes(currentLocationHostname);
        });
      }

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

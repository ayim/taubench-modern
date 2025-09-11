import { useEffect, useState } from 'react';
import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';

import { QueryProps } from './shared';

const getListWorkItemsQueryKey = ({ tenantId, agentId }: { tenantId: string; agentId?: string }) => {
  return [tenantId, 'work-items', agentId === undefined ? undefined : `aid-${agentId}`].filter(
    (item) => item !== undefined,
  );
};

const getWorkItemQueryKey = ({ tenantId, workItemId }: { tenantId: string; workItemId: string }) => {
  return [tenantId, 'work-items', workItemId];
};

export const listWorkItemsQueryOptions = ({
  tenantId,
  agentAPIClient,
  agentId,
}: QueryProps<{
  tenantId: string;
  agentId?: string;
}>) =>
  queryOptions({
    queryKey: getListWorkItemsQueryKey({ tenantId, agentId }),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/', {
        params: { query: { agent_id: agentId } },
        errorMsg: 'Failed to fetch work items',
        silent: true,
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data;
    },
  });

export const useRefreshWorkItems = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tenantId,
      agentAPIClient,
    }: QueryProps<{
      tenantId: string;
    }>) => {
      return await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/', {
        params: {},
        errorMsg: 'Failed to refresh work items',
        silent: true,
      });
    },
    onSuccess: (data, { tenantId }) => {
      // Update the query cache with the new data instead of invalidating
      queryClient.setQueryData(getListWorkItemsQueryKey({ tenantId }), data);
    },
  });
};

export const getWorkItemQueryOptions = ({
  tenantId,
  agentAPIClient,
  workItemId,
}: QueryProps<{
  tenantId: string;
  workItemId: string;
}>) =>
  queryOptions({
    queryKey: getWorkItemQueryKey({ tenantId, workItemId }),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/{work_item_id}', {
        params: { path: { work_item_id: workItemId } },
        errorMsg: `Failed to fetch work-item ${workItemId}`,
        silent: true,
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data;
    },
  });

export const useWorkItemQuery = ({ tenantId, workItemId }: { tenantId: string; workItemId: string }) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const [refetchInterval, setRefetchInterval] = useState<number | undefined>(undefined);

  const query = useQuery({
    ...getWorkItemQueryOptions({ tenantId, workItemId, agentAPIClient }),
    refetchInterval,
  });

  useEffect(() => {
    setRefetchInterval(!query.data?.thread_id ? 3000 : undefined);
  }, [query.data]);

  return query;
};

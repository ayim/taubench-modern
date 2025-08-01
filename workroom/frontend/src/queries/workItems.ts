import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { QueryProps } from './shared';

const getListWorkItemsQueryKey = (tenantId: string) => [tenantId, 'work-items'];

export const listWorkItemsQueryOptions = ({
  tenantId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: getListWorkItemsQueryKey(tenantId),
    queryFn: async () => {
      return await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/', {
        params: {},
        errorMsg: 'Failed to fetch work items',
        silent: true,
      });
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
      queryClient.setQueryData(getListWorkItemsQueryKey(tenantId), data);
    },
  });
};

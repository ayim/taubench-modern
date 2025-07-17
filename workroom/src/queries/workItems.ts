import { queryOptions } from '@tanstack/react-query';
import { QueryProps } from './shared';

export const listAgentWorkItemsQueryKey = (agentId: string) => ['workitem', agentId];

export const listAgentWorkItemsQueryOptions = ({
  tenantId,
  agentId,
  agentAPIClient,
}: QueryProps<{ agentId: string; tenantId: string }>) =>
  queryOptions({
    queryKey: listAgentWorkItemsQueryKey(agentId),
    queryFn: async () => {
      const apiResponse = await agentAPIClient.agentEventsFetch(tenantId, 'get', '/api/v1/workitems/list/', {
        params: { query: { agent_id: agentId } },
      });
      return apiResponse;
    },
  });

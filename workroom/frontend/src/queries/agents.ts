import { queryOptions } from '@tanstack/react-query';
import { QueryProps } from './shared';
import { AgentAPIClient } from '~/lib/AgentAPIClient';

export const getAgentMetaQueryKey = (agentId: string) => [agentId, 'meta'];
const getAgentQueryKey = (agentId: string) => ['agent', agentId];

export const getAgentMetaQueryOptions = ({
  agentId,
  tenantId,
  agentAPIClient,
  initialData,
}: QueryProps<{
  tenantId: string;
  agentId: string;
  initialData?: Awaited<ReturnType<AgentAPIClient['getAgentMeta']>>;
}>) =>
  queryOptions({
    queryKey: getAgentMetaQueryKey(agentId),
    queryFn: async (): ReturnType<typeof agentAPIClient.getAgentMeta> => {
      return agentAPIClient.getAgentMeta({ tenantId, agentId });
    },
    initialData,
  });

export const getAgentQueryOptions = ({
  agentId,
  tenantId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
  agentId: string;
}>) =>
  queryOptions({
    queryKey: getAgentQueryKey(agentId),
    queryFn: () => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}', {
        params: { path: { aid: agentId } },
        errorMsg: 'Agent Not Found',
      });
    },
  });

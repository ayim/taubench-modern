import { queryOptions } from '@tanstack/react-query';
import { Agent } from '~/types';
import { QueryProps } from './shared';

export const getAgentMetaQueryKey = (agentId: string) => [agentId, 'meta'];
export const getListAgentsQueryKey = (tenantId: string) => [tenantId, 'agents'];
export const getGetAgentQueryKey = (id: string) => ['agents', id];

export const getListAgentsQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: getListAgentsQueryKey(tenantId),
    queryFn: async (): Promise<Agent[]> => {
      return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/')) as Agent[];
    },
  });

export const getGetAgentQueryOptions = ({
  agentId,
  tenantId,
  agentAPIClient,
}: QueryProps<{
  agentId: string;
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: getGetAgentQueryKey(agentId),
    queryFn: async () => {
      return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}', {
        params: { path: { aid: agentId } },
        errorMsg: 'Agent Not Found',
        silent: true,
      })) as Agent;
    },
  });

export const getAgentMetaQueryOptions = ({
  agentId,
  tenantId,
  agentAPIClient,
  initialData,
}: QueryProps<{
  tenantId: string;
  agentId: string;
  initialData?: Awaited<ReturnType<typeof agentAPIClient.getAgentMeta>>;
}>) =>
  queryOptions({
    queryKey: getAgentMetaQueryKey(agentId),
    queryFn: async (): ReturnType<typeof agentAPIClient.getAgentMeta> => {
      return agentAPIClient.getAgentMeta({ tenantId, agentId });
    },
    initialData,
  });

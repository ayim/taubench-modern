import { queryOptions } from '@tanstack/react-query';
import { QueryProps } from './shared';
import { AgentAPIClient } from '~/lib/AgentAPIClient';

export const getAgentMetaQueryKey = (agentId: string) => [agentId, 'meta'];

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

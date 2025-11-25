import { queryOptions } from '@tanstack/react-query';
import { components } from '@sema4ai/agent-server-interface';
import { QueryProps } from './shared';
import { AgentAPIClient } from '~/lib/AgentAPIClient';
import { VIOLET_AGENT_METADATA } from '~/constants/violetAgent';

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

const violetAgentQueryKey = ['violetAgent', JSON.stringify(VIOLET_AGENT_METADATA)];

export const getVioletAgentQueryOptions = ({
  tenantId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: violetAgentQueryKey,
    queryFn: async (): Promise<components['schemas']['AgentCompat']> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/search/by-metadata', {
        params: { query: VIOLET_AGENT_METADATA } as never,
        errorMsg: 'Failed to locate project violet agent',
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to locate project violet agent');
      }

      const [agent] = response.data || [];

      if (!agent) {
        throw new Error('Project Violet agent not found');
      }

      return agent;
    },
  });

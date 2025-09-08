import { queryOptions, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Agent } from '@sema4ai/agent-server-interface';
import { QueryProps } from './shared';
import { useParams, useRouteContext, useRouter } from '@tanstack/react-router';
import { AgentAPIClient } from '~/lib/AgentAPIClient';

export const getAgentMetaQueryKey = (agentId: string) => [agentId, 'meta'];
export const getListAgentsQueryKey = (tenantId: string) => [tenantId, 'agents'];
export const getGetAgentQueryKey = (id: string) => ['agents', id];

export const getListAgentsQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: getListAgentsQueryKey(tenantId),
    queryFn: async (): Promise<Agent[]> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/');

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data as Agent[];
    },
  });

export const useListAgentsQuery = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useQuery(getListAgentsQueryOptions({ tenantId, agentAPIClient }));
};

export const getGetAgentQueryOptions = ({
  agentId,
  tenantId,
  agentAPIClient,
}: QueryProps<{
  agentId: string;
  tenantId: string;
  initialData?: Agent;
}>) =>
  queryOptions({
    queryKey: getGetAgentQueryKey(agentId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}', {
        params: { path: { aid: agentId } },
        errorMsg: 'Agent Not Found',
        silent: true,
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data as Agent;
    },
  });

export const useGetAgentQuery = ({
  agentId,
  tenantId,
  initialData,
}: {
  agentId: string;
  tenantId: string;
  initialData?: Agent;
}) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  return useQuery(getGetAgentQueryOptions({ agentId, tenantId, agentAPIClient, initialData }));
};

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

export const useDeleteAgentMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: async ({ tenantId, agentId }: { tenantId: string; agentId: string }) => {
      await agentAPIClient.agentFetch(tenantId, 'delete', '/api/v2/agents/{aid}', {
        params: { path: { aid: agentId } },
        errorMsg: 'Failed to delete agent',
      });
    },
    onSuccess: async (_data, { tenantId, agentId }) => {
      queryClient.setQueryData<Agent[] | undefined>(getListAgentsQueryKey(tenantId), (prev) =>
        Array.isArray(prev) ? prev.filter((a) => a.id === undefined || a.id !== agentId) : prev,
      );
      await queryClient.invalidateQueries({ queryKey: getListAgentsQueryKey(tenantId) });
      await router.invalidate();
    },
  });
};

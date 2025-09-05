import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { Agent } from '~/types';
import { QueryProps } from './shared';
import { useRouteContext, useRouter } from '@tanstack/react-router';
import { successToast, errorToast } from '~/utils/toasts';

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
      successToast('Agent deleted');
    },
    onError: () => errorToast('Failed to delete agent'),
  });
};

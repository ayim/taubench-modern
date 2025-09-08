import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';

import { QueryProps } from './shared';
import { ThreadMessage, Thread } from '@sema4ai/agent-server-interface';

export const getThreadsQueryKey = (agentId: string) => ['threads', agentId];
export const getThreadQueryKey = (tid: string) => ['thread', tid];
export const getThreadMessagesQueryKey = (tid: string) => ['thread', tid, 'messages'];

export const getThreadsQueryOptions = ({
  agentId,
  tenantId,
  agentAPIClient,
}: QueryProps<{ agentId: string; tenantId: string }>) =>
  queryOptions({
    queryKey: getThreadsQueryKey(agentId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/', {
        params: { query: { aid: agentId } },
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data as Thread[];
    },
  });

export const useThreadsQuery = ({ agentId, tenantId }: { agentId: string; tenantId: string }) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useQuery({
    ...getThreadsQueryOptions({ agentId, tenantId, agentAPIClient }),
  });
};

export const getThreadQueryOptions = ({
  threadId,
  tenantId,
  agentAPIClient,
}: QueryProps<{ threadId: string; tenantId: string }>) =>
  queryOptions({
    queryKey: getThreadQueryKey(threadId),
    queryFn: async () => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}', {
        params: { path: { tid: threadId } },
      });
    },
  });

export const useThreadQuery = ({ threadId, tenantId }: { threadId: string; tenantId: string }) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useQuery({
    ...getThreadQueryOptions({ threadId, tenantId, agentAPIClient }),
  });
};

export const getThreadMessagesQueryOptions = ({
  threadId,
  tenantId,
  agentAPIClient,
}: QueryProps<{ threadId: string; tenantId: string }>) =>
  queryOptions({
    queryKey: getThreadMessagesQueryKey(threadId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}/state', {
        params: { path: { tid: threadId } },
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data.messages as ThreadMessage[];
    },
  });

export const useThreadMessagesQuery = ({ threadId, tenantId }: { threadId: string; tenantId: string }) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useQuery({
    ...getThreadMessagesQueryOptions({ threadId, tenantId, agentAPIClient }),
  });
};

export const useCreateThreadMutation = ({ agentId, tenantId }: { agentId: string; tenantId: string }) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ name, startingMessage }: { name: string; startingMessage?: string }) => {
      return agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/threads/', {
        body: { name, agent_id: agentId, starting_message: startingMessage },
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(getThreadsQueryKey(agentId), (threads: Thread[]) => {
        return !threads ? [data] : [...threads, data];
      });
    },
  });
};

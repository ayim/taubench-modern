import { queryOptions } from '@tanstack/react-query';
import { QueryProps } from './shared';

const getThreadQueryKey = (threadId: string) => ['thread', threadId];
const getThreadsQueryKey = (agentId: string, params?: Record<string, unknown>) =>
  params ? ['threads', agentId, params] : ['threads', agentId];

export const getThreadQueryOptions = ({
  threadId,
  tenantId,
  agentAPIClient,
}: QueryProps<{
  threadId: string;
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: getThreadQueryKey(threadId),
    queryFn: () => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}', {
        params: { path: { tid: threadId } },
        errorMsg: 'Conversation Not Found',
      });
    },
  });

export const listThreadsQueryOptions = ({
  tenantId,
  agentId,
  params,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
  agentId: string;
  params?: {
    limit?: number;
  };
}>) =>
  queryOptions({
    queryKey: getThreadsQueryKey(agentId, params),
    queryFn: () => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/', {
        params: { query: { aid: agentId, ...params } },
        errorMsg: 'Failed to retrieve conversations',
      });
    },
  });

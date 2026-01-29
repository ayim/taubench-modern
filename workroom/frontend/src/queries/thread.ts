import { createSparQueryOptions } from './shared';

const getThreadQueryKey = (threadId: string) => ['thread', threadId];
const getThreadsQueryKey = (agentId: string, params?: Record<string, unknown>) => {
  return params
    ? ['threads', agentId, ...Object.entries(params).map(([key, value]) => `${key}:${value}`)]
    : ['threads', agentId];
};

export const getThreadQueryOptions = createSparQueryOptions<{ threadId: string }>()(({ agentAPIClient, threadId }) => ({
  queryKey: getThreadQueryKey(threadId),
  queryFn: () => {
    return agentAPIClient.agentFetch('get', '/api/v2/threads/{tid}', {
      params: { path: { tid: threadId } },
      errorMsg: 'Conversation Not Found',
    });
  },
}));

export const listThreadsQueryOptions = createSparQueryOptions<{ agentId: string; params?: { limit?: number } }>()(
  ({ agentAPIClient, agentId, params }) => ({
    queryKey: getThreadsQueryKey(agentId, params),
    queryFn: () => {
      return agentAPIClient.agentFetch('get', '/api/v2/threads/', {
        params: { query: { aid: agentId, ...params } },
        errorMsg: 'Failed to retrieve conversations',
      });
    },
  }),
);

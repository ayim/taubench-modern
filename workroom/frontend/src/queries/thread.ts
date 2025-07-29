import { queryOptions } from '@tanstack/react-query';
import { QueryProps } from './shared';

export const getThreadQueryKey = (tid: string) => ['thread', tid];

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

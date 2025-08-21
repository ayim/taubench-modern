import { queryOptions } from '@tanstack/react-query';
import type { paths } from '@sema4ai/agent-server-interface';
import { QueryProps } from './shared';

export type ListPlatformsResponse =
  paths['/api/v2/platforms/']['get']['responses']['200']['content']['application/json'];

export const getListPlatformsQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: ['platforms', tenantId],
    queryFn: async (): Promise<ListPlatformsResponse> => {
      return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/', {
        silent: true,
      })) as ListPlatformsResponse;
    },
  });

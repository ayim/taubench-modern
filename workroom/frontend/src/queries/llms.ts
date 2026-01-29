import { createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';

export const platformsQueryKey = () => ['platforms'];

export const platformsQueryOptions = createSparQueryOptions<object>()(({ agentAPIClient }) => ({
  queryKey: platformsQueryKey(),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/platforms/', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch MCP servers', {
        code: response.code,
        resource: ResourceType.LLMPlatform,
      });
    }

    return response.data;
  },
}));

export const usePlatformsQuery = createSparQuery(platformsQueryOptions);

import { createSparQueryOptions, createSparQuery } from './shared';

/**
 * Agent query
 */
export const agentQueryKey = (agentId: string) => ['agent', agentId];

export const agentQueryOptions = createSparQueryOptions<{ agentId: string }>()(({ sparAPIClient, agentId }) => ({
  queryKey: agentQueryKey(agentId),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/{aid}', {
      params: { path: { aid: agentId } },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to fetch agent');
    }

    return response.data;
  },
}));

export const useAgentQuery = createSparQuery(agentQueryOptions);

/**
 * Agent OAuth state query
 */
export const agentOAuthStateQueryKey = (agentId: string) => ['agentOAuthState', agentId];

export const agentOauthStateQueryOptions = createSparQueryOptions<{ agentId: string }>()(
  ({ sparAPIClient, agentId }) => ({
    queryKey: agentOAuthStateQueryKey(agentId),
    queryFn: async () => sparAPIClient.getAgentOAuthState({ agentId }),
  }),
);

export const useAgentOAuthStateQuery = createSparQuery(agentOauthStateQueryOptions);

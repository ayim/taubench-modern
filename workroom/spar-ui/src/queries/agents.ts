import { Agent } from '@sema4ai/agent-server-interface';
import { createSparQueryOptions, createSparQuery, createSparMutation } from './shared';

/**
 * List Agents query
 */
export const agentsQueryKey = () => ['agents'];

export const agentsQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: agentsQueryKey(),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/', {});

    if (!response.success) {
      throw new Error(response.message || 'Failed to fetch agents');
    }

    return response.data;
  },
}));

export const useAgentsQuery = createSparQuery(agentsQueryOptions);

/**
 * @param agentId
 * @returns
 */

/**
 * Get Agent query
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
 * Get Agent Details query
 */
export const agentDetailsQueryKey = (agentId: string) => ['agentDetails', agentId];

export const agentDetailsQueryOptions = createSparQueryOptions<{ agentId: string }>()(({ sparAPIClient, agentId }) => ({
  queryKey: agentDetailsQueryKey(agentId),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/{aid}/agent-details', {
      params: { path: { aid: agentId } },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to fetch agent details');
    }

    return response.data;
  },
}));

export const useAgentDetailsQuery = createSparQuery(agentDetailsQueryOptions);

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

/**
 * Delete Agent mutation
 */
export const useDeleteAgentMutation = createSparMutation<object, { agentId: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ agentId }) => {
      const response = await sparAPIClient.queryAgentServer('delete', '/api/v2/agents/{aid}', {
        params: { path: { aid: agentId } },
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to delete agent');
      }
    },
    onSuccess: (_, { agentId }) => {
      queryClient.setQueryData<Agent[] | undefined>(agentsQueryKey(), (prev) =>
        Array.isArray(prev) ? prev.filter((a) => a.id !== agentId) : prev,
      );
    },
  }),
);

export const useShowActionLogsMutation = createSparMutation<
  object,
  { agentId: string; threadId: string; actionServerRunId: string | null; toolCallId: string }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ agentId, threadId, actionServerRunId, toolCallId }) => {
    const response = await sparAPIClient.openActionLogs({
      agentId,
      threadId,
      toolCallId,
      actionServerRunId,
    });

    if (!response.success) {
      throw new Error(response.error.message);
    }

    return response.success;
  },
}));

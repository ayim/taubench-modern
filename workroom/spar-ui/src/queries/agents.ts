import { Agent } from '@sema4ai/agent-server-interface';
import { OAuthProvider } from '@sema4ai/oauth-client';

import { createSparQueryOptions, createSparQuery, createSparMutation, QueryError, ResourceType } from './shared';
import { AgentPackageInspectionResponse } from './agentPackageInspection';
import { AgentDeploymentFormSchema } from '../components/AgentDeploymentForm/context';

/**
 * List Agents query
 */
export const agentsQueryKey = () => ['agents'];

export const agentsQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: agentsQueryKey(),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch agents', {
        code: response.code,
        resource: ResourceType.Agent,
      });
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
      throw new QueryError(response.message || 'Failed to fetch agent', {
        code: response.code,
        resource: ResourceType.Agent,
      });
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
      throw new QueryError(response.message || 'Failed to fetch agent details', {
        code: response.code,
        resource: ResourceType.Agent,
      });
    }

    return response.data;
  },
}));

export const useAgentDetailsQuery = createSparQuery(agentDetailsQueryOptions);

/**
 * Get Agent User Interfaces query
 */
export const agentUserInterfacesQueryKey = (agentId: string) => ['agentUserInterfaces', agentId];

export const agentUserInterfacesQueryOptions = createSparQueryOptions<{ agentId: string }>()(
  ({ sparAPIClient, agentId }) => ({
    queryKey: agentUserInterfacesQueryKey(agentId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/{agent_id}/user-interfaces', {
        params: { path: { agent_id: agentId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch agent user interfaces', {
          code: response.code,
          resource: ResourceType.Agent,
        });
      }

      return response.data;
    },
  }),
);

export const useAgentUserInterfacesQuery = createSparQuery(agentUserInterfacesQueryOptions);

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
 * Search Agents by metadata
 */
export const searchAgentsByMetadataQueryKey = (metadata: Record<string, string>) => [
  'agents',
  'search-by-metadata',
  JSON.stringify(metadata),
];

export const searchAgentsByMetadataQueryOptions = createSparQueryOptions<{ metadata: Record<string, string> }>()(
  ({ sparAPIClient, metadata }) => ({
    queryKey: searchAgentsByMetadataQueryKey(metadata),
    queryFn: async () => {
      // Route not yet in the generated agent-server interface types; cast params for now
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/search/by-metadata', {
        params: { query: metadata } as never,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to find agent', {
          code: response.code,
          resource: ResourceType.Agent,
        });
      }

      return response.data;
    },
  }),
);

export const useSearchAgentsByMetadataQuery = createSparQuery(searchAgentsByMetadataQueryOptions);

/**
 * Delete Agent OAuth provider connection
 */
export const useAuthorizeAgentOAuthMutation = createSparMutation<
  { agentId: string },
  { provider: OAuthProvider; uri: string }
>()(({ agentId, queryClient, sparAPIClient }) => ({
  mutationFn: async ({ provider, uri }) => sparAPIClient.authorizeAgentOAuth({ agentId, provider, uri }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: agentOAuthStateQueryKey(agentId) });
  },
}));

/**
 * Delete Agent OAuth provider connection
 */
export const useDeleteAgentOAuthMutation = createSparMutation<
  { agentId: string },
  { provider: OAuthProvider; connectionId: string }
>()(({ agentId, queryClient, sparAPIClient }) => ({
  mutationFn: async ({ provider, connectionId }) => sparAPIClient.deleteAgentOAuth({ agentId, provider, connectionId }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: agentOAuthStateQueryKey(agentId) });
  },
}));

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
        throw new QueryError(response.message || 'Failed to delete agent', {
          code: response.code,
          resource: ResourceType.Agent,
        });
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
      throw new QueryError(response.error.message, { type: response.error.type });
    }

    return response.success;
  },
}));

export const useDeployAgentFromPackageMutation = createSparMutation<
  object,
  {
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    payload: AgentDeploymentFormSchema;
    agentPackage: File;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ agentPackage, payload }) => {
    const mcpServerIds = [...(payload.mcpServerIds ?? [])];

    const jsonPayload = {
      name: payload.name,
      description: payload.description,
      public: true,
      platform_params_ids: [payload.llmId],
      action_servers: [],
      mcp_servers: [],
      mcp_server_ids: mcpServerIds,
    };

    const formData = new FormData();
    formData.append('package_zip_file', agentPackage, agentPackage.name);

    Object.entries(jsonPayload).forEach(([fieldName, fieldValue]) => {
      const value = typeof fieldValue === 'string' ? fieldValue : JSON.stringify(fieldValue);
      formData.append(fieldName, value);
    });

    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/package/deploy/agent', {
      body: formData as never,
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to deploy agent', {
        code: response.code,
        resource: ResourceType.Agent,
      });
    }

    return response.data;
  },
}));

export const useDeployAgentMutation = createSparMutation<
  object,
  {
    payload: AgentDeploymentFormSchema;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ payload }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/agents/', {
      body: {
        name: payload.name,
        agent_architecture: {
          name: 'agent',
          version: 'V2.0',
        },
        version: '1.0.0',
        mode: payload.mode,
        runbook: payload.runbook,
        description: payload.description || 'My agent',
        public: true,
        platform_params_ids: [payload.llmId],
        mcp_server_ids: payload.mcpServerIds,
      },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to deploy agent', {
        code: response.code,
        resource: ResourceType.Agent,
      });
    }

    return response.data.agent_id;
  },
}));

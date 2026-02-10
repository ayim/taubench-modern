import { Agent } from '@sema4ai/agent-server-interface';

import { createSparQueryOptions, createSparQuery, createSparMutation, QueryError, ResourceType } from './shared';
import { AgentPackageInspectionResponse } from './agentPackageInspection';
import { agentPackageSecretsToHeaderEntries } from '../utils/actionPackages';
import { AgentDeploymentFormSchema } from '../components/AgentDeploymentForm/context';
import { formHeadersToApiHeaders } from '../components/MCPServers/schemas/mcpFormSchema';
import { AgentDetailsSchema } from '../components/ChatDetails/components/context';

/**
 * List Agents query
 */
export const agentsQueryKey = () => ['agents'];

export const agentsQueryOptions = createSparQueryOptions<object>()(({ agentAPIClient }) => ({
  queryKey: agentsQueryKey(),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/agents/', {});

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

export const agentQueryOptions = createSparQueryOptions<{ agentId: string }>()(({ agentAPIClient, agentId }) => ({
  queryKey: agentQueryKey(agentId),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/agents/{aid}', {
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

export const agentDetailsQueryOptions = createSparQueryOptions<{ agentId: string }>()(
  ({ agentAPIClient, agentId }) => ({
    queryKey: agentDetailsQueryKey(agentId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch('get', '/api/v2/agents/{aid}/agent-details', {
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
  }),
);

export const useAgentDetailsQuery = createSparQuery(agentDetailsQueryOptions);

/**
 * Get Agent User Interfaces query
 */
export const agentUserInterfacesQueryKey = (agentId: string) => ['agentUserInterfaces', agentId];

export const agentUserInterfacesQueryOptions = createSparQueryOptions<{ agentId: string }>()(
  ({ agentAPIClient, agentId }) => ({
    queryKey: agentUserInterfacesQueryKey(agentId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch('get', '/api/v2/agents/{agent_id}/user-interfaces', {
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
  ({ agentAPIClient, agentId }) => ({
    queryKey: agentOAuthStateQueryKey(agentId),
    queryFn: async () => agentAPIClient.getAgentPermissions({ agentId }),
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
  ({ agentAPIClient, metadata }) => ({
    queryKey: searchAgentsByMetadataQueryKey(metadata),
    queryFn: async () => {
      // Route not yet in the generated agent-server interface types; cast params for now
      const response = await agentAPIClient.agentFetch('get', '/api/v2/agents/search/by-metadata', {
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
 * Update Agent mutation
 */
export const useUpdateAgentMutation = createSparMutation<{ agentId: string }, { payload: AgentDetailsSchema }>()(
  ({ agentAPIClient, queryClient, agentId }) => ({
    mutationFn: async ({ payload }) => {
      const response = await agentAPIClient.agentFetch('put', '/api/v2/agents/{aid}', {
        params: { path: { aid: agentId } },
        body: payload,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to update agent', {
          code: response.code,
          resource: ResourceType.Agent,
        });
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsQueryKey() });
      queryClient.invalidateQueries({ queryKey: agentQueryKey(agentId) });
      queryClient.invalidateQueries({ queryKey: agentDetailsQueryKey(agentId) });
    },
  }),
);
/**
 * Delete Agent OAuth provider connection
 */
export const useDeleteAgentOAuthMutation = createSparMutation<{ agentId: string }, { connectionId: string }>()(
  ({ agentId, queryClient, agentAPIClient }) => ({
    mutationFn: async ({ connectionId }) => agentAPIClient.deleteOAuthConnection({ agentId, connectionId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentOAuthStateQueryKey(agentId) });
    },
  }),
);

/**
 * Delete Agent mutation
 */
export const useDeleteAgentMutation = createSparMutation<object, { agentId: string }>()(
  ({ agentAPIClient, queryClient }) => ({
    mutationFn: async ({ agentId }) => {
      const response = await agentAPIClient.agentFetch('delete', '/api/v2/agents/{aid}', {
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
  { agentId: string; threadId: string; toolCallId: string }
>()(({ agentAPIClient }) => ({
  mutationFn: async ({ agentId, threadId, toolCallId }) => {
    const response = await agentAPIClient.getActionLogHtml({ agentId, threadId, toolCallId });

    if (!response.success) {
      return response;
    }

    const actionLogsWindow = window.open();

    if (!actionLogsWindow) {
      return {
        success: false,
        error: {
          message: 'Unable to open the action logs',
        },
      };
    }

    actionLogsWindow.document.write(response.data.html);
    actionLogsWindow.document.close();

    return { success: true };
  },
}));

export const useDeployAgentFromPackageMutation = createSparMutation<
  object,
  {
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    payload: AgentDeploymentFormSchema;
    agentPackage: File;
  }
>()(({ agentAPIClient }) => ({
  mutationFn: async ({ agentTemplate, agentPackage, payload }) => {
    const mcpServerIds = [...(payload.mcpServerIds ?? [])];
    const hasActionPackages = (agentTemplate.action_packages ?? []).length > 0;

    if (hasActionPackages) {
      const headerEntries = payload.agentPackageSecrets
        ? agentPackageSecretsToHeaderEntries(payload.agentPackageSecrets)
        : undefined;
      const headers = headerEntries ? formHeadersToApiHeaders(headerEntries) : undefined;

      const mcpFormData = new FormData();
      mcpFormData.append('file', agentPackage);
      mcpFormData.append('name', `${payload.name} - Actions`);
      mcpFormData.append('headers', JSON.stringify(headers));
      mcpFormData.append('mcp_server_metadata', JSON.stringify(agentTemplate));

      const response = await agentAPIClient.agentFetch('post', '/api/v2/mcp-servers/', {
        body: mcpFormData as never,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to create hosted MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      mcpServerIds.push(response.data.mcp_server_id);
    }

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

    const response = await agentAPIClient.agentFetch('post', '/api/v2/package/deploy/agent', {
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
>()(({ agentAPIClient, queryClient }) => ({
  mutationFn: async ({ payload }) => {
    const response = await agentAPIClient.agentFetch('post', '/api/v2/agents/', {
      body: {
        name: payload.name,
        agent_architecture: {
          name: 'agent_platform.architectures.experimental_1',
          version: '2.0.0',
        },
        version: '1.0.0',
        mode: payload.mode,
        runbook: payload.runbook,
        description: payload.description || 'My agent',
        public: true,
        platform_params_ids: [payload.llmId],
        mcp_server_ids: payload.mcpServerIds,
        document_intelligence: 'v2.1',
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
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: agentsQueryKey() });
  },
}));

/**
 * List Agent Architectures query
 */
export const agentArchitecturesQueryKey = () => ['agentArchitectures'];

export const agentArchitecturesQueryOptions = createSparQueryOptions<object>()(({ agentAPIClient }) => ({
  queryKey: agentArchitecturesQueryKey(),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/capabilities/architectures', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch agent architectures', {
        code: response.code,
        resource: ResourceType.Agent,
      });
    }

    return response.data as {
      name: string;
      summary: string;
      version: string;
    }[];
  },
}));

export const useAgentArchitecturesQuery = createSparQuery(agentArchitecturesQueryOptions);

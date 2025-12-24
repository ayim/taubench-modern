import type { components } from '@sema4ai/agent-server-interface';
import {
  createSparQueryOptions,
  createSparQuery,
  createSparMutation,
  QueryError,
  ResourceType,
  ServerRequest,
} from './shared';

export type McpServer = components['schemas']['MCPServerResponse'];
export type McpServerCreate = ServerRequest<'post', '/api/v2/mcp-servers/', 'requestBody'>;
export type McpServerUpdate = ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>;

export const mcpServersQueryKey = () => ['mcp-servers'];
export const mcpServerQueryKey = (mcpServerId: string) => ['mcp-server', mcpServerId];

export const mcpServersQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: mcpServersQueryKey(),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/mcp-servers/', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch MCP servers', {
        code: response.code,
        resource: ResourceType.McpServer,
      });
    }

    return response.data;
  },
}));

export const useMcpServersQuery = createSparQuery(mcpServersQueryOptions);

export const getMCPServerQueryOptions = createSparQueryOptions<{ mcpServerId: string }>()(
  ({ sparAPIClient, mcpServerId }) => ({
    queryKey: mcpServerQueryKey(mcpServerId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
  }),
);

export const useMcpServerQuery = createSparQuery(getMCPServerQueryOptions);

export const useCreateMcpServerMutation = createSparMutation<object, { body: McpServerCreate }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ body }) => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/mcp-servers/', {
        body,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to create MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mcpServersQueryKey() });
    },
  }),
);

export const useUpdateMcpServerMutation = createSparMutation<object, { mcpServerId: string; body: McpServerUpdate }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ mcpServerId, body }) => {
      const response = await sparAPIClient.queryAgentServer('put', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        body,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to update MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
    onSuccess: (mcpServer, { mcpServerId }) => {
      queryClient.setQueryData(mcpServersQueryKey(), (prev: Record<string, McpServer> | undefined) => ({
        ...(prev ?? {}),
        [mcpServer.mcp_server_id]: mcpServer,
      }));
      queryClient.invalidateQueries({ queryKey: mcpServerQueryKey(mcpServerId) });
    },
  }),
);

export const useDeleteMcpServerMutation = createSparMutation<object, { mcpServerId: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ mcpServerId }) => {
      const response = await sparAPIClient.queryAgentServer('delete', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to delete MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
    onSuccess: (_response, { mcpServerId }) => {
      queryClient.setQueryData(mcpServersQueryKey(), (prev: Record<string, McpServer> | undefined) => {
        if (!prev) return prev;
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { [mcpServerId]: _removed, ...rest } = prev;
        return rest;
      });
    },
  }),
);

/**
 * Create Hosted MCP Server mutation (with file upload)
 *
 * This mutation uploads an agent package ZIP file and creates a hosted MCP server.
 * Only available in Workroom (not Studio).
 */
export const useCreateHostedMcpServerMutation = createSparMutation<
  object,
  {
    name: string;
    file: File;
    headers?: McpServerCreate['headers'];
    mcpServerMetadata?: Record<string, unknown>;
  }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ name, file, headers, mcpServerMetadata }) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    if (headers) {
      formData.append('headers', JSON.stringify(headers));
    }
    if (mcpServerMetadata) {
      formData.append('mcp_server_metadata', JSON.stringify(mcpServerMetadata));
    }

    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/mcp-servers/mcp-servers-hosted', {
      body: formData as never,
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to create hosted MCP server', {
        code: response.code,
        resource: ResourceType.McpServer,
      });
    }

    return response.data;
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: mcpServersQueryKey() });
  },
}));

export const useValidateMcpServerCapabilitiesMutation = createSparMutation<object, { mcpServer: McpServerCreate }>()(
  ({ sparAPIClient }) => ({
    mutationFn: async ({ mcpServer }) => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/capabilities/mcp/tools', {
        body: { mcp_servers: [mcpServer] },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to validate MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      const results = response.data?.results ?? [];
      const allIssues = results.flatMap((result) => result.issues ?? []);
      if (allIssues.length > 0) {
        throw new QueryError(allIssues.join('; '), { resource: ResourceType.McpServer });
      }

      return response.data;
    },
  }),
);

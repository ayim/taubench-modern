import type { ServerRequest, ServerResponse } from '@sema4ai/agent-server-interface';
import { createSparQueryOptions, createSparQuery, createSparMutation, QueryError, ResourceType } from './shared';

export const mcpServersQueryKey = () => ['mcp-servers'];
export const mcpServerQueryKey = (mcpServerId: string) => ['mcp-server', mcpServerId];
export type ListMcpServersResponse = ServerResponse<'get', '/api/v2/mcp-servers/'>;

export const mcpServersQueryOptions = createSparQueryOptions<object>()(({ agentAPIClient }) => ({
  queryKey: mcpServersQueryKey(),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/mcp-servers/', {});

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

export type McpServerGetResponse = ServerResponse<'get', '/api/v2/mcp-servers/{mcp_server_id}'>;

export const getMCPServerQueryOptions = createSparQueryOptions<{ mcpServerId: string }>()(
  ({ agentAPIClient, mcpServerId }) => ({
    queryKey: mcpServerQueryKey(mcpServerId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch('get', '/api/v2/mcp-servers/{mcp_server_id}', {
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

type McpServerCreateInput = ServerRequest<'post', '/api/v2/mcp-servers/', 'requestBody'>;

export const useCreateMcpServerMutation = createSparMutation<object, { body: McpServerCreateInput }>()(
  ({ agentAPIClient, queryClient }) => ({
    mutationFn: async ({ body }) => {
      const response = await agentAPIClient.agentFetch('post', '/api/v2/mcp-servers/', {
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

type McpServerUpdate = ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>;
type McpServerUpdateResponse = ServerResponse<'put', '/api/v2/mcp-servers/{mcp_server_id}'>;

export const useUpdateMcpServerMutation = createSparMutation<object, { mcpServerId: string; body: McpServerUpdate }>()(
  ({ agentAPIClient, queryClient }) => ({
    mutationFn: async ({ mcpServerId, body }) => {
      const response = await agentAPIClient.agentFetch('put', '/api/v2/mcp-servers/{mcp_server_id}', {
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
      queryClient.setQueryData(mcpServersQueryKey(), (prev: Record<string, McpServerUpdateResponse> | undefined) => ({
        ...(prev ?? {}),
        [mcpServer.mcp_server_id]: mcpServer,
      }));
      queryClient.invalidateQueries({ queryKey: mcpServerQueryKey(mcpServerId) });
    },
  }),
);

type McpServerDeleteResponse = ServerResponse<'delete', '/api/v2/mcp-servers/{mcp_server_id}'>;

export const useDeleteMcpServerMutation = createSparMutation<object, { mcpServerId: string }>()(
  ({ agentAPIClient, queryClient }) => ({
    mutationFn: async ({ mcpServerId }) => {
      const response = await agentAPIClient.agentFetch('delete', '/api/v2/mcp-servers/{mcp_server_id}', {
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
      queryClient.setQueryData(mcpServersQueryKey(), (prev: Record<string, McpServerDeleteResponse> | undefined) => {
        if (!prev) return prev;
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { [mcpServerId]: _removed, ...rest } = prev;
        return rest;
      });
    },
  }),
);

export type McpServerCreateResponse = ServerResponse<'post', '/api/v2/mcp-servers/'>;
export type { McpServerCreateInput };

export const useValidateMcpServerCapabilitiesMutation = createSparMutation<
  object,
  { mcpServer: McpServerCreateInput }
>()(({ agentAPIClient }) => ({
  mutationFn: async ({ mcpServer }) => {
    const response = await agentAPIClient.agentFetch('post', '/api/v2/capabilities/mcp/tools', {
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
}));

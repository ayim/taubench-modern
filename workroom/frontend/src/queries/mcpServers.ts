import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import type { components, paths } from '@sema4ai/agent-server-interface';
import { QueryProps } from './shared';
import { useRouteContext } from '@tanstack/react-router';
import { transformMcpServerForEditing } from './agent-interface-patches';

// Semantic type aliases for better naming
export type MCPServer = components['schemas']['MCPServerResponse'];
export type MCPServerCreate = paths['/api/v2/mcp-servers/']['post']['requestBody']['content']['application/json'];
export type MCPServerEdit =
  paths['/api/v2/mcp-servers/{mcp_server_id}']['put']['requestBody']['content']['application/json'];
export type ListMCPServersResponse =
  paths['/api/v2/mcp-servers/']['get']['responses']['200']['content']['application/json'];

export const getListMcpServersQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: ['mcp-servers', tenantId],
    queryFn: async (): Promise<ListMCPServersResponse> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/mcp-servers/', {
        silent: true,
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data;
    },
  });

export const useDeleteMcpServerMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ tenantId, mcpServerId }: { tenantId: string; mcpServerId: string }) => {
      await agentAPIClient.agentFetch(tenantId, 'delete', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        errorMsg: 'Failed to delete MCP server',
      });
    },
    onSuccess: async (_data, { tenantId }) => {
      await queryClient.invalidateQueries({ queryKey: ['mcp-servers', tenantId] });
    },
  });
};

export const useCreateMcpServerMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ tenantId, body }: { tenantId: string; body: MCPServerCreate }) => {
      return await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/mcp-servers/', {
        body,
        silent: true,
      });
    },
    onSuccess: async (_data, { tenantId }) => {
      await queryClient.invalidateQueries({ queryKey: ['mcp-servers', tenantId] });
    },
  });
};

export const getMcpServerQueryOptions = ({
  tenantId,
  mcpServerId,
  agentAPIClient,
}: QueryProps<{ tenantId: string; mcpServerId: string }>) =>
  queryOptions({
    queryKey: ['mcp-server', tenantId, mcpServerId],
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        silent: true,
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return transformMcpServerForEditing(response.data);
    },
  });

export const useUpdateMcpServerMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tenantId,
      mcpServerId,
      body,
    }: {
      tenantId: string;
      mcpServerId: string;
      body: MCPServerEdit;
    }) => {
      const response = await agentAPIClient.agentFetch(tenantId, 'put', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        body,
        errorMsg: 'Failed to update MCP server',
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return transformMcpServerForEditing(response.data);
    },
    onSuccess: async (_data, { tenantId, mcpServerId }) => {
      await queryClient.invalidateQueries({ queryKey: ['mcp-servers', tenantId] });
      await queryClient.invalidateQueries({ queryKey: ['mcp-server', tenantId, mcpServerId] });
    },
  });
};

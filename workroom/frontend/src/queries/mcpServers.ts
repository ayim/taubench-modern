import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { components, paths } from '@sema4ai/agent-server-interface';
import { useRouteContext } from '@tanstack/react-router';
import { QueryProps } from './shared';

export type McpServer = components['schemas']['MCPServerResponse'];
type CreateMcpServerBody = paths['/api/v2/mcp-servers/']['post']['requestBody']['content']['application/json'];

const mcpServersQueryKey = (tenantId: string) => ['mcp-servers', tenantId];
const mcpServerQueryKey = (tenantId: string, mcpServerId: string) => ['mcp-server', tenantId, mcpServerId];

export const getListMcpServersQueryOptions = ({
  tenantId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: mcpServersQueryKey(tenantId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/mcp-servers/', {
        params: {},
        errorMsg: 'Failed to fetch MCP servers',
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to fetch MCP servers');
      }

      return response.data;
    },
  });

export const getMcpServerQueryOptions = ({
  tenantId,
  mcpServerId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
  mcpServerId: string;
}>) =>
  queryOptions({
    queryKey: mcpServerQueryKey(tenantId, mcpServerId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        errorMsg: 'Failed to fetch MCP server',
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to fetch MCP server');
      }

      return response.data;
    },
  });

export const useListMcpServersQuery = ({ tenantId }: { tenantId: string }) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  return useQuery(getListMcpServersQueryOptions({ tenantId, agentAPIClient }));
};

export const useDeleteMcpServerMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ tenantId, mcpServerId }: { tenantId: string; mcpServerId: string }) => {
      const response = await agentAPIClient.agentFetch(tenantId, 'delete', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        errorMsg: 'Failed to delete MCP server',
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to delete MCP server');
      }

      return response.data;
    },
    onSuccess: (_data, { tenantId }) => {
      queryClient.invalidateQueries({ queryKey: mcpServersQueryKey(tenantId) });
    },
  });
};

export const useCreateMcpServerMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ tenantId, body }: { tenantId: string; body: CreateMcpServerBody }) => {
      const response = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/mcp-servers/', {
        body,
        errorMsg: 'Failed to create MCP server',
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to create MCP server');
      }

      return response.data;
    },
    onSuccess: (mcpServer, { tenantId }) => {
      queryClient.setQueryData(mcpServersQueryKey(tenantId), (mcpServers: Record<string, McpServer> | undefined) => {
        return { ...(mcpServers ?? {}), [mcpServer.mcp_server_id]: mcpServer };
      });
    },
  });
};

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
      body: paths['/api/v2/mcp-servers/{mcp_server_id}']['put']['requestBody']['content']['application/json'];
    }) => {
      const response = await agentAPIClient.agentFetch(tenantId, 'put', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        body,
        errorMsg: 'Failed to update MCP server',
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to update MCP server');
      }

      return response.data;
    },
    onSuccess: (mcpServer, { tenantId, mcpServerId }) => {
      queryClient.setQueryData(mcpServersQueryKey(tenantId), (mcpServers: Record<string, McpServer> | undefined) => {
        return { ...(mcpServers ?? {}), [mcpServer.mcp_server_id]: mcpServer };
      });
      queryClient.invalidateQueries({ queryKey: mcpServerQueryKey(tenantId, mcpServerId) });
    },
  });
};

export const useCreateHostedMcpServerMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tenantId,
      name,
      file,
      headers,
      mcpServerMetadata,
    }: {
      tenantId: string;
      name: string;
      file: File;
      headers?: CreateMcpServerBody['headers'];
      mcpServerMetadata?: Record<string, unknown>;
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', name);
      if (headers) {
        formData.append('headers', JSON.stringify(headers));
      }
      if (mcpServerMetadata) {
        formData.append('mcp_server_metadata', JSON.stringify(mcpServerMetadata));
      }

      const response = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/mcp-servers/mcp-servers-hosted', {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        body: formData as any,
        errorMsg: 'Failed to create hosted MCP server',
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to create hosted MCP server');
      }

      return response.data;
    },
    onSuccess: (mcpServer, { tenantId }) => {
      queryClient.setQueryData(mcpServersQueryKey(tenantId), (mcpServers: Record<string, McpServer> | undefined) => {
        return { ...(mcpServers ?? {}), [mcpServer.mcp_server_id]: mcpServer };
      });
    },
  });
};

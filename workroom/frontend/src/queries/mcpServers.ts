import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import type { components, paths } from '@sema4ai/agent-server-interface';
import { QueryProps } from './shared';
import { useRouteContext } from '@tanstack/react-router';

export type ListMcpServersResponse =
  paths['/api/v2/mcp-servers/']['get']['responses']['200']['content']['application/json'];
export type McpServerResponse = components['schemas']['MCPServerResponse'];

export const getListMcpServersQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: ['mcp-servers', tenantId],
    queryFn: async (): Promise<ListMcpServersResponse> => {
      return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/mcp-servers/', {
        silent: true,
      })) as ListMcpServersResponse;
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

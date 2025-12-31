import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';
import { QueryProps } from './shared';
import type { ServerResponse } from '@sema4ai/agent-server-interface';

const mcpServersQueryKey = (tenantId: string) => ['mcp-servers', tenantId];

export type ListMcpServersResponse = ServerResponse<'get', '/api/v2/mcp-servers/'>;
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

import { Outlet, createFileRoute, useNavigate, useParams, useRouteContext } from '@tanstack/react-router';
import { useQueryClient, useSuspenseQuery } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

import { Box, Button, Dialog, Header, Scroll } from '@sema4ai/components';
import { McpServersTable } from '~/components/platforms/mcpServers/components/McpServersTable';
import { getListMcpServersQueryOptions, useDeleteMcpServerMutation } from '~/queries/mcpServers';

export const Route = createFileRoute('/tenants/$tenantId/mcp-servers/')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId } }) =>
    queryClient.ensureQueryData(getListMcpServersQueryOptions({ agentAPIClient, tenantId })),
  component: RouteComponent,
});

function RouteComponent() {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/mcp-servers/' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const [deleteTarget, setDeleteTarget] = useState<{ id: string } | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const deleteMutation = useDeleteMcpServerMutation();

  const { data } = useSuspenseQuery(getListMcpServersQueryOptions({ agentAPIClient, tenantId }));

  const response =
    data ?? (queryClient.getQueryData(['mcp-servers', tenantId]) as ReturnType<typeof Route.useLoaderData>);
  const items = (response ? Object.values(response) : []).map((srv) => ({
    id: srv.mcp_server_id,
    name: srv.name,
    transport: srv.transport,
    source: srv.source,
    url: srv.url ?? null,
    command: (srv as unknown as { command?: string | null })?.command ?? null,
  }));

  const onSearchQueryUpdate = useCallback(
    (searchQuery: string) => {
      const params = new URLSearchParams(searchQuery.startsWith('?') ? searchQuery : `?${searchQuery}`);
      const nextSearch: Record<string, unknown> = {};
      params.forEach((_v, key) => {
        const all = params.getAll(key);
        nextSearch[key] = all.length > 1 ? all : params.get(key);
      });
      navigate({ to: '.', search: (prev) => ({ ...(prev as Record<string, unknown>), ...nextSearch }) });
    },
    [navigate],
  );

  return (
    <>
      <Scroll>
        <Box p="$24" pb="$48">
          <Header size="x-large">
            <Header.Title title="MCP servers" />
            <Header.Description>Manage MCP servers</Header.Description>
          </Header>

          <Box borderWidth="1px" borderColor="grey80" borderRadius="$8" p="$16" mb="$32" backgroundColor="white">
            <Box mt="$8">
              <McpServersTable
                items={items}
                onQuery={onSearchQueryUpdate}
                onCreate={() => navigate({ to: '/tenants/$tenantId/mcp-servers/new', params: { tenantId } })}
                onDelete={(i) => setDeleteTarget(i)}
              />
            </Box>
          </Box>
        </Box>
      </Scroll>
      {deleteTarget && (
        <Dialog open onClose={() => setDeleteTarget(null)}>
          <Dialog.Header>
            <Dialog.Header.Title title="Are you sure?" />
          </Dialog.Header>
          <Dialog.Content>Deleting an MCP server will remove its configuration. This cannot be undone.</Dialog.Content>
          <Dialog.Actions>
            <Button
              variant="primary"
              loading={deleteMutation.isPending}
              onClick={async () => {
                if (!deleteTarget) return;
                await deleteMutation.mutateAsync({ tenantId, mcpServerId: deleteTarget.id });
                setDeleteTarget(null);
              }}
            >
              Delete
            </Button>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
          </Dialog.Actions>
        </Dialog>
      )}
      <Outlet />
    </>
  );
}

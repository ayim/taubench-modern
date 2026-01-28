import { useCallback } from 'react';
import { Outlet, createFileRoute, useNavigate } from '@tanstack/react-router';

import { McpServersTable } from './mcp-servers/components/McpServersTable';
import { useMcpServersQuery } from '~/queries/mcpServers';
import { Page } from '~/components/layout/Page';

export const Route = createFileRoute('/tenants/$tenantId/mcp-servers')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { data: mcpServersById = {} } = useMcpServersQuery({});
  const mcpServers = Object.values(mcpServersById);

  const onSearchQueryUpdate = useCallback(
    (searchQuery: string) => {
      const params = new URLSearchParams(searchQuery.startsWith('?') ? searchQuery : '?${searchQuery}');
      const nextSearch: Record<string, unknown> = {};
      params.forEach((_v, key) => {
        const all = params.getAll(key);
        nextSearch[key] = all.length > 1 ? all : params.get(key);
      });
      navigate({ to: '.', search: (prev: Record<string, unknown>) => ({ ...prev, ...nextSearch }) });
    },
    [navigate],
  );

  return (
    <Page title="MCP servers">
      <McpServersTable items={mcpServers} onQuery={onSearchQueryUpdate} />
      <Outlet />
    </Page>
  );
}

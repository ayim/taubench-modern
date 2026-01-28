import { FC } from 'react';
import { Box, Button } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { useNavigate, useParams } from '@tanstack/react-router';

import { ListMcpServersResponse } from '~/queries/mcpServers';
import { Row } from './McpServersRow';

export const getServerTypeLabel = (server: ListMcpServersResponse[string]): string => {
  if (server.is_hosted) return 'Hosted';
  if (server.url) return 'Remote';
  if (server.command) return 'Local';
  return '—';
};

type Props = {
  items: ListMcpServersResponse[string][];
  onQuery?: (searchQuery: string) => void;
};

// TODO: Confirm columns to display
export const McpServersTable: FC<Props> = ({ items, onQuery }) => {
  const navigate = useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  const onCreate = () => {
    navigate({ to: '/tenants/$tenantId/mcp-servers/new', params: { tenantId } });
  };

  const filterConfiguration: TableWithFilterConfiguration<ListMcpServersResponse[string]> = {
    id: 'mcp-servers',
    label: { singular: 'MCP server', plural: 'MCP servers' },
    columns: [
      { id: 'name', title: 'Name', sortable: true, required: true },
      { id: 'type', title: 'Type', sortable: true, width: 100 },
      { id: 'url', title: 'URL', sortable: true },
      { id: 'actions', title: '', sortable: false, width: 32 },
    ],
    sort: ['name', 'asc'],
    searchRules: {
      name: { value: (item) => item.name },
      type: { value: (item) => getServerTypeLabel(item) },
      url: { value: (item) => item.url ?? '' },
    },
    sortRules: {
      name: { type: 'string', value: (item) => item.name },
      type: { type: 'string', value: (item) => getServerTypeLabel(item) },
      url: { type: 'string', value: (item) => item.url ?? '' },
    },
    contentBefore: (
      <Box display="flex" gap="$8" alignItems="center">
        <Button icon={IconPlus} round onClick={onCreate}>
          MCP server
        </Button>
      </Box>
    ),
  };

  return (
    <Box>
      <TableWithFilter {...filterConfiguration} onQuery={onQuery} data={items} row={Row} />
    </Box>
  );
};

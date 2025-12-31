import { FC } from 'react';
import { Box, Button } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { useNavigate, useParams } from '@tanstack/react-router';

import { Row } from './McpServersRow';
import { ListMcpServersResponse } from '~/queries/mcpServers';

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
      { id: 'transport', title: 'Transport', sortable: true },
      { id: 'url', title: 'URL', sortable: true },
      { id: 'actions', title: '', sortable: false, width: 32 },
    ],
    sort: ['name', 'asc'],
    searchRules: {
      name: { value: (item) => item.name },
      transport: { value: (item) => item.transport },
      source: { value: (item) => item.source },
      url: { value: (item) => item.url ?? '' },
      command: { value: (item) => item.command ?? '' },
    },
    sortRules: {
      name: { type: 'string', value: (item) => item.name },
      transport: { type: 'string', value: (item) => item.transport },
      source: { type: 'string', value: (item) => item.source },
      url: { type: 'string', value: (item) => item.url ?? '' },
      command: { type: 'string', value: (item) => item.command ?? '' },
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

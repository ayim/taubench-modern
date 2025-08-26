import type { TableRowProps } from '@sema4ai/components';
import { Box, Button, Menu, Table } from '@sema4ai/components';
import { IconDotsHorizontal, IconPlus } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { FC } from 'react';

type McpServerTableItem = {
  id: string;
  name: string;
  transport: string;
  source: string;
  url?: string | null;
  command?: string | null;
};

type Props = {
  items: McpServerTableItem[];
  onCreate?: () => void;
  onEdit?: (item: McpServerTableItem) => void;
  onDelete?: (item: McpServerTableItem) => void;
  onQuery?: (searchQuery: string) => void;
};

// TODO: Confirm columns to display
export const McpServersTable: FC<Props> = ({ items, onCreate, onEdit, onDelete, onQuery }) => {
  const Row: FC<TableRowProps<McpServerTableItem>> = ({ rowData }) => (
    <Table.Row onClick={onEdit ? () => onEdit?.(rowData) : undefined}>
      <Table.Cell>{rowData.name}</Table.Cell>
      <Table.Cell>{rowData.transport}</Table.Cell>
      <Table.Cell>{rowData.source}</Table.Cell>
      <Table.Cell>{rowData.url ?? ''}</Table.Cell>
      <Table.Cell>{rowData.command ?? ''}</Table.Cell>
      <Table.Cell controls>
        {(onEdit || onDelete) && (
          <Menu trigger={<Button aria-label="action" icon={IconDotsHorizontal} variant="ghost" size="small" />}>
            {onEdit && <Menu.Item onClick={() => onEdit?.(rowData)}>Edit</Menu.Item>}
            {onDelete && <Menu.Item onClick={() => onDelete?.(rowData)}>Delete</Menu.Item>}
          </Menu>
        )}
      </Table.Cell>
    </Table.Row>
  );

  const filterConfiguration: TableWithFilterConfiguration<McpServerTableItem> = {
    id: 'mcp-servers',
    label: { singular: 'MCP server', plural: 'MCP servers' },
    columns: [
      { id: 'name', title: 'Name', sortable: true, required: true },
      { id: 'transport', title: 'Transport', sortable: true },
      { id: 'source', title: 'Source', sortable: true },
      { id: 'url', title: 'URL', sortable: true },
      { id: 'command', title: 'Command', sortable: true },
      { id: 'actions', title: '', sortable: false },
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
        {onCreate && (
          <Button icon={IconPlus} round onClick={onCreate}>
            MCP server
          </Button>
        )}
      </Box>
    ),
  };

  return (
    <Box>
      <TableWithFilter {...filterConfiguration} onQuery={onQuery} data={items} row={Row} />
    </Box>
  );
};

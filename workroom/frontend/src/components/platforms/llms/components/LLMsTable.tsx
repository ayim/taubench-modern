import type { TableRowProps } from '@sema4ai/components';
import { Box, Button, Menu, Select, Table } from '@sema4ai/components';
import { IconDotsHorizontal, IconPlus } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { FC, useState } from 'react';
import { formatDatetime } from '~/lib/utils';
import { PROVIDERS } from './llmSchemas';

export type LLMTableItem = {
  id: string;
  name: string;
  provider: string;
  model: string;
  createdAt?: string;
};

type Props = {
  items: LLMTableItem[];
  onCreate?: () => void;
  onEdit?: (item: LLMTableItem) => void;
  onDelete?: (item: LLMTableItem) => void;
  selectable?: boolean;
  selectedId?: string | null;
  onSelect?: (item: LLMTableItem) => void;
};

type Provider = (typeof PROVIDERS)[number];

export const LLMsTable: FC<Props> = ({
  items,
  onCreate,
  onEdit,
  onDelete,
  selectable = false,
  selectedId = null,
  onSelect,
}) => {
  const [providerFilter, setProviderFilter] = useState<'all' | Provider>('all');
  const Row: FC<TableRowProps<LLMTableItem>> = ({ rowData }) => (
    <Table.Row
      onClick={selectable && onSelect ? () => onSelect(rowData) : onEdit ? () => onEdit?.(rowData) : undefined}
      aria-selected={selectable && selectedId === rowData.id}
    >
      <Table.Cell>{rowData.name}</Table.Cell>
      <Table.Cell>{rowData.provider}</Table.Cell>
      <Table.Cell>{rowData.model}</Table.Cell>
      <Table.Cell>{rowData.createdAt ? formatDatetime(rowData.createdAt) : ''}</Table.Cell>
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

  const filterConfiguration: TableWithFilterConfiguration<LLMTableItem> = {
    id: 'llms',
    label: { singular: 'LLM', plural: 'LLMs' },
    columns: [
      { id: 'name', title: 'Name', sortable: true, required: true },
      { id: 'provider', title: 'Provider', sortable: true },
      { id: 'model', title: 'Model', sortable: true },
      { id: 'createdAt', title: 'Created at', sortable: true },
      { id: 'actions', title: '', sortable: false },
    ],
    sort: ['createdAt', 'desc'],
    searchRules: {
      name: { value: (item) => item.name },
      provider: { value: (item) => item.provider },
      model: { value: (item) => item.model },
    },
    sortRules: {
      name: { type: 'string', value: (item) => item.name },
      provider: { type: 'string', value: (item) => item.provider },
      model: { type: 'string', value: (item) => item.model },
      createdAt: { type: 'date', value: (item) => item.createdAt ?? '' },
    },
    contentBefore: (
      <Box display="flex" gap="$8" alignItems="center">
        {onCreate && (
          <Button icon={IconPlus} round onClick={onCreate}>
            LLM
          </Button>
        )}
        <Select
          aria-label="Provider filter"
          items={[
            { value: 'all', label: 'All providers' },
            ...Array.from(PROVIDERS).map((provider) => ({
              value: provider,
              label: provider.charAt(0).toUpperCase() + provider.slice(1),
            })),
          ]}
          value={providerFilter}
          onChange={(selectedProvider) => {
            const isValidProvider = (value: string): value is 'all' | Provider => {
              return value === 'all' || value === 'openai' || value === 'azure' || value === 'bedrock';
            };
            if (isValidProvider(selectedProvider)) {
              setProviderFilter(selectedProvider);
            }
          }}
        />
      </Box>
    ),
  };

  const filteredItems =
    providerFilter === 'all' ? items : items.filter((i) => i.provider.toLowerCase() === providerFilter);

  return (
    <Box>
      <TableWithFilter {...filterConfiguration} data={filteredItems} row={Row} />
    </Box>
  );
};

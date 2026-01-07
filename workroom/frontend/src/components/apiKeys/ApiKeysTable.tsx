import { type FC, useCallback } from 'react';
import type { TableRowProps } from '@sema4ai/components';
import { Box, Button, Menu, Table, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconCheck2, IconCopy, IconDotsHorizontal, IconGlobe, IconPlus } from '@sema4ai/icons';
import { TableWithFilter, type TableWithFilterConfiguration, useDeleteConfirm } from '@sema4ai/layouts';
import { useNavigate } from '@tanstack/react-router';
import { formatDatetime } from '~/lib/utils';
import { trpc } from '~/lib/trpc';

export type ApiKeyTableItem = {
  id: string;
  name: string;
  createdAt: string;
  lastUsedAt: string | null;
};

type RowExtraProps = {
  tenantId: string;
};

const Row: FC<TableRowProps<ApiKeyTableItem, RowExtraProps>> = ({ rowData, props: { tenantId } }) => {
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();
  const trpcUtils = trpc.useUtils();
  const deleteMutation = trpc.apiKeys.remove.useMutation();

  const handleEdit = () => {
    navigate({ to: '/tenants/$tenantId/configuration/api-keys/$apiKeyId', params: { tenantId, apiKeyId: rowData.id } });
  };

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: rowData.name,
      entityType: 'API key',
    },
    [],
  );

  const onDelete = onDeleteConfirm(() => {
    deleteMutation.mutate(
      { id: rowData.id },
      {
        onSuccess: () => {
          trpcUtils.apiKeys.list.invalidate();
          addSnackbar({ message: 'API Key Deleted', variant: 'success' });
        },
        onError: (error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  });

  return (
    <Table.Row onClick={handleEdit}>
      <Table.Cell>{rowData.name}</Table.Cell>
      <Table.Cell>{formatDatetime(rowData.createdAt)}</Table.Cell>
      <Table.Cell>{rowData.lastUsedAt ? formatDatetime(rowData.lastUsedAt) : 'Never'}</Table.Cell>
      <Table.Cell controls>
        <Menu trigger={<Button aria-label="action" icon={IconDotsHorizontal} variant="ghost" size="small" />}>
          <Menu.Item onClick={handleEdit}>Edit</Menu.Item>
          <Menu.Item onClick={onDelete}>Delete</Menu.Item>
        </Menu>
      </Table.Cell>
    </Table.Row>
  );
};

type Props = {
  items: ApiKeyTableItem[];
  tenantId: string;
};

export const ApiKeysTable: FC<Props> = ({ items, tenantId }) => {
  const navigate = useNavigate();
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();

  const handleCreate = useCallback(() => {
    navigate({ to: '/tenants/$tenantId/configuration/api-keys/new', params: { tenantId } });
  }, [navigate, tenantId]);

  const endpointUrl = `${window.location.origin}/tenants/${tenantId}/api/v1`;

  const filterConfiguration: TableWithFilterConfiguration<ApiKeyTableItem> = {
    id: 'api-keys',
    label: { singular: 'API Key', plural: 'API Keys' },
    columns: [
      { id: 'name', title: 'Name', sortable: true, required: true },
      { id: 'createdAt', title: 'Created', sortable: true },
      { id: 'lastUsedAt', title: 'Last Used', sortable: true },
      { id: 'actions', title: '', sortable: false, required: true, width: 32 },
    ],
    sort: ['createdAt', 'desc'],
    searchRules: {
      name: { value: (item) => item.name },
    },
    sortRules: {
      name: { type: 'string', value: (item) => item.name },
      createdAt: { type: 'date', value: (item) => item.createdAt },
      lastUsedAt: { type: 'date', value: (item) => item.lastUsedAt ?? '' },
    },
    contentBefore: (
      <Box display="flex" gap="$8" alignItems="center">
        <Button icon={IconPlus} round onClick={handleCreate}>
          API Key
        </Button>
        <Button icon={IconGlobe} variant="secondary" round onClick={onCopyToClipboard(endpointUrl)}>
          Copy Endpoint URL
          <Box alignItems="center" pl="$4">
            {copiedToClipboard ? <IconCheck2 /> : <IconCopy />}
          </Box>
        </Button>
      </Box>
    ),
  };

  return <TableWithFilter {...filterConfiguration} data={items} row={Row} rowProps={{ tenantId }} />;
};

import { FC } from 'react';
import type { TableRowProps } from '@sema4ai/components';
import { Badge, Box, Button, Menu, Table, useSnackbar } from '@sema4ai/components';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { useDeleteConfirm } from '@sema4ai/layouts';

import { MenuLink } from '../../../../common/link';
import { useNavigate } from '../../../../hooks';
import { DataConnectionIcon } from '../../components/DataConnectionIcon';
import { useDeleteDataConnectionMutation } from '../../../../queries/dataConnections';
import { DataConnectionRowItem } from './types';
import { formatDatetime } from '../../../../lib/utils';

type DataAccessRowProps = TableRowProps<DataConnectionRowItem, { organizationName?: string }>;

export const DataConnectionRow: FC<DataAccessRowProps> = ({ rowData, props: { organizationName } }) => {
  const navigate = useNavigate();
  const { mutate: deleteDataConnection } = useDeleteDataConnectionMutation({ dataConnectionId: rowData.id });
  const { addSnackbar } = useSnackbar();
  const isDataConnectionUsedByDocumentIntelligence = rowData.tags?.[0] === 'data_intelligence';

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: rowData.name,
      entityType: 'data-connection',
    },
    [],
  );

  const onEdit = () => {
    navigate({ to: '/data-connections/$dataConnectionId', params: { dataConnectionId: rowData.id } });
  };

  const onDelete = onDeleteConfirm(() => {
    deleteDataConnection(
      { dataConnectionId: rowData.id },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Data connection deleted successfully',
            variant: 'success',
          });
        },
        onError: (error: unknown) => {
          addSnackbar({
            message: error instanceof Error ? error.message : 'Failed to delete Data Connection',
            variant: 'danger',
          });
        },
      },
    );
  });

  return (
    <Table.Row onClick={rowData.isOrganizationalConnection ? undefined : onEdit}>
      <Table.Cell>
        <Box display="flex" alignItems="center" gap="$8">
          {rowData.name}
          {isDataConnectionUsedByDocumentIntelligence && (
            <Badge
              size="small"
              variant="info"
              label="Document Intelligence"
              aria-description="This data connection is used for Document Intelligence"
            />
          )}
        </Box>
      </Table.Cell>
      <Table.Cell>
        <Box display="flex" alignItems="center" gap="$8">
          <DataConnectionIcon engine={rowData.engine} />
          {rowData.engine}
        </Box>
      </Table.Cell>
      <Table.Cell>
        {rowData.isOrganizationalConnection ? (
          <Badge aria-description="Organizational" variant="brand-primary" label={organizationName} size="small" />
        ) : (
          <Badge aria-description="Local" variant="success" label="Local" size="small" />
        )}
      </Table.Cell>
      <Table.Cell>{rowData.description}</Table.Cell>
      <Table.Cell>{rowData.created_at ? formatDatetime(rowData.created_at) : '-'}</Table.Cell>
      <Table.Cell controls>
        {!rowData.isOrganizationalConnection && (
          <Menu trigger={<Button aria-label="Actions" icon={IconDotsHorizontal} variant="ghost" size="small" />}>
            <MenuLink to="/data-connections/$dataConnectionId" params={{ dataConnectionId: rowData.id }}>
              Edit
            </MenuLink>
            <Menu.Item onClick={onDelete}>Delete</Menu.Item>
          </Menu>
        )}
      </Table.Cell>
    </Table.Row>
  );
};

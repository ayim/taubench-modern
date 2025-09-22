import { FC } from 'react';
import type { TableRowProps } from '@sema4ai/components';
import { Box, Button, Menu, Table, useSnackbar } from '@sema4ai/components';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { useConfirmAction } from '@sema4ai/layouts';

import { MenuLink } from '../../../../common/link';
import { useNavigate } from '../../../../hooks';
import { DataConnectionIcon } from '../../components/DataConnectionIcon';
import { DataConnection, useDeleteDataConnectionMutation } from '../../../../queries/dataConnections';

type DataAccessRowProps = TableRowProps<DataConnection>;

export const DataConnectionRow: FC<DataAccessRowProps> = ({ rowData }) => {
  const navigate = useNavigate();
  const { mutate: deleteDataConnection } = useDeleteDataConnectionMutation({ dataConnectionId: rowData.id });
  const { addSnackbar } = useSnackbar();

  const onDeleteConfirm = useConfirmAction(
    {
      title: `Delete Data Connection`,
      text: `Are you sure you want to delete "${rowData.name}"? This action cannot be undone.`,
      confirmActionText: 'Delete',
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
    <Table.Row onClick={onEdit}>
      <Table.Cell>{rowData.name}</Table.Cell>
      <Table.Cell>
        <Box display="flex" alignItems="center" gap="$8">
          <DataConnectionIcon engine={rowData.engine} />
          {rowData.engine}
        </Box>
      </Table.Cell>
      <Table.Cell>{rowData.description}</Table.Cell>
      <Table.Cell controls>
        <Menu trigger={<Button aria-label="Actions" icon={IconDotsHorizontal} variant="ghost" size="small" />}>
          <MenuLink to="/data-connections/$dataConnectionId" params={{ dataConnectionId: rowData.id }}>
            Edit
          </MenuLink>
          <Menu.Item onClick={onDelete}>Delete</Menu.Item>
        </Menu>
      </Table.Cell>
    </Table.Row>
  );
};

import { FC } from 'react';
import { Button, Menu, Table, TableRowProps, useSnackbar } from '@sema4ai/components';
import { useNavigate, useParams } from '@tanstack/react-router';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { useDeleteConfirm } from '@sema4ai/layouts';

import { McpServer, useDeleteMcpServerMutation } from '~/queries/mcpServers';

export const Row: FC<TableRowProps<McpServer>> = ({ rowData }) => {
  const navigate = useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { addSnackbar } = useSnackbar();

  const { mutate: deleteMcpServer } = useDeleteMcpServerMutation();

  const onEdit = () => {
    navigate({
      to: '/tenants/$tenantId/mcp-servers/$mcpServerId',
      params: { tenantId, mcpServerId: rowData.mcp_server_id },
    });
  };

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: rowData.name,
      entityType: 'mcp-server',
    },
    [],
  );

  const onDelete = onDeleteConfirm(() => {
    deleteMcpServer(
      { tenantId, mcpServerId: rowData.mcp_server_id },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'MCP server deleted successfully',
            variant: 'success',
          });
        },
        onError: () => {
          addSnackbar({
            message: 'Failed to delete MCP server',
            variant: 'danger',
          });
        },
      },
    );
  });

  return (
    <Table.Row onClick={onEdit}>
      <Table.Cell>{rowData.name}</Table.Cell>
      <Table.Cell>{rowData.transport}</Table.Cell>
      <Table.Cell>{rowData.url ?? ''}</Table.Cell>
      <Table.Cell controls>
        <Menu trigger={<Button aria-label="action" icon={IconDotsHorizontal} variant="ghost" size="small" />}>
          {onEdit && <Menu.Item onClick={onEdit}>Edit</Menu.Item>}
          {onDelete && <Menu.Item onClick={onDelete}>Delete</Menu.Item>}
        </Menu>
      </Table.Cell>
    </Table.Row>
  );
};

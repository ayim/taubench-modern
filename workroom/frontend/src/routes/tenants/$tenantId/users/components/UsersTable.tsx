import { FC, useMemo } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { Box, Button, Menu, Table, TableRowProps } from '@sema4ai/components';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { IconDotsVertical } from '@sema4ai/icons';
import { TrpcOutput } from '~/lib/trpc';

type Users = TrpcOutput['userManagement']['listUsers']['users'];
type Props = {
  tenantId: string;
  items: Users;
  canUpdateUsers: boolean;
};

const roleLabels: Record<Users[number]['role'], string> = {
  admin: 'Admin',
  operator: 'Operator',
  knowledgeWorker: 'Knowledge Worker',
  agentSupervisor: 'Agent Supervisor',
};

const filterConfiguration: TableWithFilterConfiguration<Users[number]> = {
  id: 'users',
  label: { singular: 'User', plural: 'Users' },
  columns: [
    { id: 'firstName', title: 'First Name', sortable: true, required: true },
    { id: 'lastName', title: 'Last Name', sortable: true },
    { id: 'role', title: 'Role', sortable: true },
  ],
  sort: ['firstName', 'asc'],
  searchRules: {
    firstName: { value: (item) => item.firstName },
    lastName: { value: (item) => item.lastName },
    role: { value: (item) => item.role },
  },
  sortRules: {
    firstName: { type: 'string', value: (item) => item.firstName },
    lastName: { type: 'string', value: (item) => item.lastName },
    role: { type: 'string', value: (item) => item.role },
  },
};

const TableRow: FC<TableRowProps<Users[number], { canUpdateUsers: boolean; tenantId: string }>> = ({
  rowData,
  props: { canUpdateUsers, tenantId },
}) => {
  const navigate = useNavigate();
  return (
    <Table.Row>
      <Table.Cell>{rowData.firstName}</Table.Cell>
      <Table.Cell>{rowData.lastName}</Table.Cell>
      <Table.Cell>{roleLabels[rowData.role] ?? rowData.role}</Table.Cell>
      {canUpdateUsers && (
        <Table.Cell controls>
          <Menu trigger={<Button aria-label="action" icon={IconDotsVertical} variant="ghost" size="small" />}>
            <Menu.Item
              onClick={() =>
                navigate({
                  to: '/tenants/$tenantId/users/$userId/update',
                  params: { tenantId, userId: rowData.id },
                })
              }
            >
              Update
            </Menu.Item>
          </Menu>
        </Table.Cell>
      )}
    </Table.Row>
  );
};

export const UsersTable: FC<Props> = ({ items, tenantId, canUpdateUsers }) => {
  const enhancedFilterConfiguration = useMemo(() => {
    return {
      ...filterConfiguration,
      columns: [
        ...filterConfiguration.columns,
        ...(canUpdateUsers ? [{ id: 'actions', title: '', width: 32, required: true }] : []),
      ],
      filters: {
        role: {
          label: 'Role',
          searchable: true,
          closeMenuOnItemSelect: true,
          options: Array.from(new Set(items.map((item) => item.role))).map((role) => ({
            label: roleLabels[role] ?? role,
            value: role,
            itemType: 'checkbox',
          })),
        },
      },
    };
  }, [items, canUpdateUsers]);

  const rowProps = useMemo(
    () => ({
      tenantId,
      canUpdateUsers,
    }),
    [tenantId, canUpdateUsers],
  );

  return (
    <Box>
      <TableWithFilter {...enhancedFilterConfiguration} data={items} row={TableRow} rowProps={rowProps} />
    </Box>
  );
};

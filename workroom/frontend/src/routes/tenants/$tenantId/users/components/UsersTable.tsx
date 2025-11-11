import { FC, useMemo } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { Box, Button, Menu, Table, TableRowProps } from '@sema4ai/components';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { IconDotsVertical } from '@sema4ai/icons';
import { TrpcOutput } from '~/lib/trpc';

type Users = TrpcOutput['userManagement']['listUsers']['users'];
type Props = {
  canUpdateUsers: boolean;
  items: Users;
  roleLabels: RoleLabels;
  tenantId: string;
};

export type RoleLabels = Record<Users[number]['role'], string>;

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

const TableRow: FC<
  TableRowProps<Users[number], { canUpdateUsers: boolean; roleLabels: RoleLabels; tenantId: string }>
> = ({ rowData, props: { canUpdateUsers, roleLabels, tenantId } }) => {
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

export const UsersTable: FC<Props> = ({ canUpdateUsers, items, roleLabels, tenantId }) => {
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
  }, [canUpdateUsers, items, roleLabels]);

  const rowProps = useMemo(
    () => ({
      canUpdateUsers,
      roleLabels,
      tenantId,
    }),
    [canUpdateUsers, roleLabels, tenantId],
  );

  return (
    <Box>
      <TableWithFilter {...enhancedFilterConfiguration} data={items} row={TableRow} rowProps={rowProps} />
    </Box>
  );
};

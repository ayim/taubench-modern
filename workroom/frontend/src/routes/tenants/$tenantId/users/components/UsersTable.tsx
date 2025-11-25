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
  providerIdentifierType: 'id' | 'email';
  roleLabels: RoleLabels;
  tenantId: string;
};

export type RoleLabels = Record<Users[number]['role'], string>;

const getFilterConfiguration = ({
  providerIdentifierType,
}: Pick<Props, 'providerIdentifierType'>): TableWithFilterConfiguration<Users[number]> => ({
  id: 'users',
  label: { singular: 'User', plural: 'Users' },
  columns: [
    { id: 'firstName', title: 'First Name', sortable: true, required: true },
    { id: 'lastName', title: 'Last Name', sortable: true },
    { id: 'providerIdentifier', title: providerIdentifierType === 'email' ? 'Email' : 'Authority ID', sortable: true },
    { id: 'role', title: 'Role', sortable: true },
  ],
  sort: ['firstName', 'asc'],
  searchRules: {
    firstName: { value: (item) => item.firstName },
    lastName: { value: (item) => item.lastName },
    role: { value: (item) => item.role },
    providerIdentifier: {
      value: (item) =>
        item.providerIdentifier.type === 'email' ? item.providerIdentifier.email : item.providerIdentifier.id,
    },
  },
  sortRules: {
    firstName: { type: 'string', value: (item) => item.firstName },
    lastName: { type: 'string', value: (item) => item.lastName },
    role: { type: 'string', value: (item) => item.role },
    providerIdentifier: {
      type: 'string',
      value: (item) =>
        item.providerIdentifier.type === 'email' ? item.providerIdentifier.email : item.providerIdentifier.id,
    },
  },
});

const TableRow: FC<
  TableRowProps<Users[number], { canUpdateUsers: boolean; roleLabels: RoleLabels; tenantId: string }>
> = ({ rowData, props: { canUpdateUsers, roleLabels, tenantId } }) => {
  const navigate = useNavigate();
  return (
    <Table.Row>
      <Table.Cell>{rowData.firstName}</Table.Cell>
      <Table.Cell>{rowData.lastName}</Table.Cell>
      <Table.Cell>
        {rowData.providerIdentifier.type === 'email' ? rowData.providerIdentifier.email : rowData.providerIdentifier.id}
      </Table.Cell>
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

export const UsersTable: FC<Props> = ({ canUpdateUsers, items, providerIdentifierType, roleLabels, tenantId }) => {
  const enhancedFilterConfiguration = useMemo(() => {
    const filterConfiguration = getFilterConfiguration({ providerIdentifierType });

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
  }, [canUpdateUsers, items, providerIdentifierType, roleLabels]);

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

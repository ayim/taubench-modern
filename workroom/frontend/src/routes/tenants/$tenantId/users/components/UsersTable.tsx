import type { TableRowProps } from '@sema4ai/components';
import { Box, Table } from '@sema4ai/components';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { FC } from 'react';
import { TrpcOutput } from '~/lib/trpc';

type Users = TrpcOutput['userManagement']['listUsers']['users'];
type Props = {
  items: Users;
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

const TableRow: FC<TableRowProps<Users[number]>> = ({ rowData }) => {
  return (
    <Table.Row>
      <Table.Cell>{rowData.firstName}</Table.Cell>
      <Table.Cell>{rowData.lastName}</Table.Cell>
      <Table.Cell>{rowData.role}</Table.Cell>
    </Table.Row>
  );
};

export const UsersTable: FC<Props> = ({ items }) => {
  return (
    <Box>
      <TableWithFilter {...filterConfiguration} data={items} row={TableRow} />
    </Box>
  );
};

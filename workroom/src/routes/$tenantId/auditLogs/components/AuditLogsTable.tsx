import { FC } from 'react';
import { Table, TableRowProps, Tooltip } from '@sema4ai/components';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { components as workroomComponents } from '@sema4ai/workroom-interface';

import { formatDatetime } from '~/lib/utils';
import { Details } from './Details';

type Item = workroomComponents['schemas']['AuditLog'];

const TableCell = styled(Table.Cell)`
  vertical-align: top;
  padding-top: ${({ theme }) => theme.space.$16};
`;

const getActionDetails = (item: Item) => {
  switch (item.type) {
    case 'action_invoked':
      return {
        label: 'Action invoked',
        details: (
          <Details>
            <Details.Label>Action:</Details.Label>
            <Details.Content>{item.details.actionName}</Details.Content>
            <Details.Label>Invocation ID:</Details.Label>
            <Details.Content>{item.details.invocationId}</Details.Content>
            {item.details.agentId && (
              <>
                <Details.Label>Agent ID:</Details.Label>
                <Details.Content>{item.details.agentId}</Details.Content>
              </>
            )}
            {item.details.agentThreadId && (
              <>
                <Details.Label>Thread ID:</Details.Label>
                <Details.Content>{item.details.agentThreadId}</Details.Content>
              </>
            )}
            {item.details.invokedOnBehalfOfUserId && (
              <>
                <Details.Label>Invoked in behalf of User ID:</Details.Label>
                <Details.Content>{item.details.invokedOnBehalfOfUserId}</Details.Content>
              </>
            )}
          </Details>
        ),
      };
    default:
      return {
        label: item.type,
        details: <></>,
      };
  }
};

const getActorDetails = (item: Item) => {
  switch (item.actor.type) {
    case 'agent':
      return (
        <Tooltip text={`Agent ID: ${item.actor.id}`} $nowrap>
          <span>Agent</span>
        </Tooltip>
      );
  }
};

const filterConfiguration: TableWithFilterConfiguration<Item> = {
  id: 'audit-logs',
  label: {
    singular: 'Log',
    plural: 'Logs',
  },
  columns: [
    {
      title: 'Type',
      id: 'type',
      sortable: true,
      required: true,
    },
    {
      title: 'Date',
      id: 'createdAt',
      sortable: true,
    },
    {
      title: 'Actor',
      id: 'actor',
      sortable: true,
    },
    {
      title: 'Details',
      id: 'details',
      sortable: false,
    },
  ],
  sort: ['createdAt', 'desc'],
  searchRules: {
    action: { value: (item) => item.type },
    details: { value: (item) => JSON.stringify(Object.values(item.details)) },
  },
  sortRules: {
    action: {
      type: 'string',
      value: (item) => item.type,
    },
    createdAt: {
      type: 'date',
      value: (item) => item.createdAt,
    },
    actor: {
      type: 'string',
      value: (item) => item.actor.id,
    },
  },
};

type Props = {
  auditLogs: Item[];
};

const Row: FC<TableRowProps<Item>> = ({ rowData }) => {
  const { label, details } = getActionDetails(rowData);

  return (
    <Table.Row>
      <TableCell valign="top">{label}</TableCell>
      <TableCell valign="top">{formatDatetime(rowData.createdAt)}</TableCell>
      <TableCell>{getActorDetails(rowData)}</TableCell>
      <TableCell>{details}</TableCell>
    </Table.Row>
  );
};

export const AuditLogsTable: FC<Props> = ({ auditLogs }) => {
  return <TableWithFilter {...filterConfiguration} data={auditLogs} row={Row} />;
};

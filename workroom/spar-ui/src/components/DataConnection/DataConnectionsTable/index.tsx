import { FC } from 'react';
import { Box, EmptyState, Progress, Typography } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';

import { useDataConnectionsQuery } from '../../../queries/dataConnections';
import { ButtonLink } from '../../../common/link/ButtonLink';
import { DataConnectionRow } from './components/DataConnectionRow';
import type { DataConnectionRowItem } from './components/types';

type Props = {
  organizationalConnections?: DataConnectionRowItem[];
  organizationName?: string;
};

export const DataConnectionTable: FC<Props> = ({ organizationalConnections, organizationName }) => {
  const { data: dataSources = [], isLoading } = useDataConnectionsQuery({});

  const filterConfiguration: TableWithFilterConfiguration<DataConnectionRowItem> = {
    id: 'data-connections',
    label: { singular: 'Data Connection', plural: 'Data Connections' },
    columns: [
      { id: 'name', title: 'Name', sortable: true, required: true },
      { id: 'engine', title: 'Type', sortable: true },
      { id: 'source', title: 'Source', sortable: true },
      { id: 'description', title: 'Description', sortable: false },
      { id: 'created_at', title: 'Created At', sortable: true },
      { id: 'actions', title: '', width: 32, required: true },
    ],
    sort: ['name', 'asc'],
    searchRules: {
      name: { value: (item) => item.name },
      engine: { value: (item) => item.engine },
      description: { value: (item) => item.description },
    },
    sortRules: {
      name: { type: 'string', value: (item) => item.name },
      engine: { type: 'string', value: (item) => item.engine },
      source: { type: 'string', value: (item) => (item.isOrganizationalConnection ? 'Organizational' : 'Local') },
      created_at: { type: 'date', value: (item) => item.created_at },
    },
    filters: {
      model: {
        label: 'Engine',
        searchable: true,
        closeMenuOnItemSelect: true,
        options: Array.from(new Set(dataSources.map((item) => item.engine))).map((engine) => ({
          label: engine,
          value: engine,
          itemType: 'checkbox',
        })),
      },
    },
  };

  if (isLoading) {
    return <Progress variant="page" />;
  }

  const data = organizationalConnections
    ? [...organizationalConnections.map((item) => ({ ...item, isOrganizationalConnection: true })), ...dataSources]
    : dataSources;

  if (data.length === 0) {
    return (
      <Box display="flex" flex="1" justifyContent="center" flexDirection="column" maxHeight={960}>
        <EmptyState
          title="Data Connections"
          description="Store Connection Details that can be used to configure agent's data sources."
          action={
            <ButtonLink to="/data-connections/create" params={{}} round>
              Add Connection Details
            </ButtonLink>
          }
        >
          <Typography>No data connections found</Typography>
        </EmptyState>
      </Box>
    );
  }

  return (
    <TableWithFilter
      contentBefore={
        <Box display="flex" gap="$8" alignItems="center">
          <ButtonLink to="/data-connections/create" params={{}} icon={IconPlus} round>
            Data Connection
          </ButtonLink>
        </Box>
      }
      {...filterConfiguration}
      data={data}
      row={DataConnectionRow}
      rowProps={{ organizationName }}
    />
  );
};

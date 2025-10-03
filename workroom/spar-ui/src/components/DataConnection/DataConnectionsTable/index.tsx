import { Box, EmptyState, Progress, Typography } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';

import { DataConnection, useDataConnectionsQuery } from '../../../queries/dataConnections';
import { ButtonLink } from '../../../common/link/ButtonLink';
import { DataConnectionRow } from './components/DataConnectionRow';

export const DataConnectionTable = () => {
  const { data: dataSources = [], isLoading } = useDataConnectionsQuery({});

  const filterConfiguration: TableWithFilterConfiguration<DataConnection> = {
    id: 'data-connections',
    label: { singular: 'Data Connection', plural: 'Data Connections' },
    columns: [
      { id: 'name', title: 'Name', sortable: true, required: true },
      { id: 'engine', title: 'Type', sortable: true },
      { id: 'description', title: 'Description', sortable: false },
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

  if (dataSources.length === 0) {
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
      data={dataSources}
      row={DataConnectionRow}
    />
  );
};

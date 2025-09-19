import type { TableRowProps } from '@sema4ai/components';
import { Box, Button } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { FC, useState, useMemo } from 'react';
import { DataAccessRow, DataSourceItem } from "./components/DataConnectionRow";
import { DataAccessActions } from "./components/DataConnectionActions";
import { DataConnectionFilter } from "./components/DataConnectionFilter";
import { useDataConnectionsQuery } from '../../queries/dataConnections';

const createDataSourceRowWithHandlers = (
  onEdit?: (item: DataSourceItem) => void, 
  onDelete?: (item: DataSourceItem) => void
): FC<TableRowProps<DataSourceItem>> => {
  return ({ rowData, ...rest }) => (
    <DataAccessRow {...rest} rowData={rowData} onEdit={onEdit} onDelete={onDelete} />
  );
};


export const DataConnectionTable = () => {
  const [providerFilter, setProviderFilter] = useState<string>('all');

  const { data: dataSources = [] } = useDataConnectionsQuery({});
  const RowWithHandlers = createDataSourceRowWithHandlers(
    DataAccessActions.handleEdit, 
    DataAccessActions.handleDelete
  );

  const filteredData = useMemo(() => {
    return providerFilter === 'all' 
      ? dataSources 
      : dataSources.filter((item) => item.engine === providerFilter);
  }, [dataSources, providerFilter]);

  
  const filterConfiguration: TableWithFilterConfiguration<DataSourceItem> = {
    id: 'data-connections',
    label: { singular: 'Data Connection', plural: 'Data Connections' },
    columns: [
      { id: 'name', title: 'Name', sortable: true, required: true },
      { id: 'engine', title: 'Type', sortable: true },
      { id: 'description', title: 'Description', sortable: false },
      { id: 'createdAt', title: 'Created At', sortable: true },
      { id: 'updatedAt', title: 'Updated At', sortable: true },
      { id: 'actions', title: '', sortable: false },
    ],
    sort: ['name', 'asc'],
    searchRules: {
      name: { value: (item) => item.name },
      engine: { value: (item) => item.engine },
      description: { value: (item) => item.description },
      createdAt: { value: (item) => item.created_at },
      updatedAt: { value: (item) => item.updated_at },
    },
    sortRules: {
      name: { type: 'string', value: (item) => item.name },
      engine: { type: 'string', value: (item) => item.engine },
    },
    contentBefore: (
      <Box display="flex" gap="$8" alignItems="center">
        <Button icon={IconPlus} round onClick={DataAccessActions.handleCreate}>
          Data Connection
        </Button>
        <DataConnectionFilter
          dataSources={dataSources}
          providerFilter={providerFilter}
          onProviderFilterChange={setProviderFilter}
        />
      </Box>
    ),
  };

  return (
    <TableWithFilter {...filterConfiguration} data={filteredData} row={RowWithHandlers} />
  );
};
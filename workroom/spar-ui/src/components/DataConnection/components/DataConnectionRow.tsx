import type { TableRowProps } from '@sema4ai/components';
import { Box, Button, Menu, Table } from '@sema4ai/components';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { FC } from 'react';
import { DataConnectionIcon } from "./DataConnectionIcon";
import type { DataConnection } from '../../../queries/dataConnections';

export type DataSourceItem = DataConnection;

type DataAccessRowProps = TableRowProps<DataSourceItem> & {
  onEdit?: (item: DataSourceItem) => void;
  onDelete?: (item: DataSourceItem) => void;
};


export const DataAccessRow: FC<DataAccessRowProps> = ({ 
  rowData, 
  onEdit, 
  onDelete 
}) => (
  <Table.Row onClick={onEdit ? () => onEdit(rowData) : undefined}>
    <Table.Cell>{rowData.name}</Table.Cell>
    <Table.Cell>
      <Box display="flex" alignItems="center" gap="$8">
        <DataConnectionIcon engine={rowData.engine} />
        {rowData.engine}
      </Box>
    </Table.Cell>
    <Table.Cell>{rowData.description}</Table.Cell>
    <Table.Cell>{rowData.created_at}</Table.Cell>
    <Table.Cell>{rowData.updated_at}</Table.Cell>
    <Table.Cell controls>
      {(onEdit || onDelete) && (
        <Menu trigger={<Button aria-label="Actions" icon={IconDotsHorizontal} variant="ghost" size="small" />}>
          {onEdit && <Menu.Item onClick={() => onEdit(rowData)}>Edit</Menu.Item>}
          {onDelete && <Menu.Item onClick={() => onDelete(rowData)}>Delete</Menu.Item>}
        </Menu>
      )}
    </Table.Cell>
  </Table.Row>
);

export type { DataAccessRowProps };

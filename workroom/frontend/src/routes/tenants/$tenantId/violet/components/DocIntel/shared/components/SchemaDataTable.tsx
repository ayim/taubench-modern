import { Table, Column, TableRowProps } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { FC } from 'react';

const StyledTable = styled(Table)`
  border: none !important;
  background: none !important;
  min-width: 100%;

  table {
    border: none !important;
    background: none !important;
  }

  tr {
    border: none !important;
    border-bottom: none !important;
  }

  th {
    border: none !important;
  }

  td {
    border: none !important;
    background-color: transparent !important;
    background: transparent !important;
  }

  thead {
    border-bottom: 1px solid #d1d5db !important;
  }
` as typeof Table;

const StyledSchemaDataTable = styled(StyledTable)`
  overflow: hidden;
` as typeof Table;

export interface SchemaDataTableProps<TData, TRowProps> {
  columns: Column[];
  data: TData[];
  row: FC<TableRowProps<TData, TRowProps>>;
  rowProps?: TRowProps;
  selectable?: boolean;
  selected?: string[];
  onSelect?: (selected: string[] | ((prev: string[]) => string[])) => void;
  layout?: 'auto' | 'fixed';
  rowCount?: 'all' | number;
  keyId?: (row: TData) => string;
}

// Main SchemaDataTable component for editable tables (fields, columns)
export const SchemaDataTable = <TData, TRowProps>({
  columns,
  data,
  row,
  rowProps,
  selectable = true,
  selected = [],
  onSelect,
  layout = 'auto',
  rowCount = 'all',
  keyId,
}: SchemaDataTableProps<TData, TRowProps>) => {
  const handleSelect = (selectedItems: string[] | ((prev: string[]) => string[])) => {
    if (onSelect) {
      onSelect(selectedItems);
    }
  };

  return (
    <StyledTable
      selectable={selectable}
      selected={selected}
      onSelect={handleSelect}
      columns={columns}
      data={data}
      row={row}
      rowProps={rowProps}
      layout={layout}
      rowCount={rowCount}
      keyId={keyId}
    />
  );
};

// SchemaDataDisplayTable component for read-only data display
export const SchemaDataDisplayTable = <TData,>({
  columns,
  data,
  row,
  layout = 'auto',
  rowCount = 'all',
}: Omit<SchemaDataTableProps<TData, never>, 'selectable' | 'selected' | 'onSelect' | 'rowProps'>) => {
  return <StyledSchemaDataTable columns={columns} data={data} row={row} layout={layout} rowCount={rowCount} />;
};

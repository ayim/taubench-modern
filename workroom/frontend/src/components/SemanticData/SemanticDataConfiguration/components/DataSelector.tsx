import { TreeList } from '@sema4ai/layouts';
import { Box, Button, Typography } from '@sema4ai/components';
import { components } from '@sema4ai/agent-server-interface';
import { IconDbColumn, IconDbDatabase, IconDbSpreadsheet } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';

import { DataConnectionFormSchema, tablesToDataSelection } from './form';

export const DataSelector = ({
  data,
}: {
  data: components['schemas']['agent_platform__core__payloads__data_connection__TableInfo'][];
}) => {
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const { dataSelection = [], fileRefId } = watch();

  const isColumnSelected = (tableName: string, columnName: string) => {
    const tableSelection = dataSelection.find((selection) => selection.name === tableName);
    return !!tableSelection && tableSelection.columns.findIndex((column) => column.name === columnName) > -1;
  };

  const isTableSelected = (tableName: string): boolean | 'partial' => {
    const tableSelection = dataSelection.find((selection) => selection.name === tableName);
    if (!tableSelection) {
      return false;
    }

    if (tableSelection.columns.length === 0) {
      return false;
    }

    const selectedColumns = data
      .find((curr) => curr.name === tableName)
      ?.columns.filter((col) => tableSelection.columns.findIndex((column) => column.name === col.name) > -1);

    return selectedColumns?.length === data.find((curr) => curr.name === tableName)?.columns.length ? true : 'partial';
  };

  const toggleColumnSelection = (
    tableName: string,
    column: components['schemas']['agent_platform__core__payloads__data_connection__ColumnInfo'],
  ) => {
    const columnDefinition = {
      name: column.name,
      data_type: column.data_type,
      sample_values: column.sample_values || undefined,
      description: column.description || '',
      synonyms: column.synonyms || undefined,
    };

    const nextSelection = (() => {
      const existingIndex = dataSelection.findIndex((curr) => curr.name === tableName);

      if (existingIndex === -1) {
        return [...dataSelection, { name: tableName, columns: [columnDefinition] }];
      }

      const { columns, ...rest } = dataSelection[existingIndex];

      const updatedColumns =
        columns.findIndex((curr) => curr.name === column.name) > -1
          ? columns.filter((c) => c.name !== column.name)
          : [...columns, columnDefinition];

      if (updatedColumns.length === 0) {
        return dataSelection.filter((s) => s.name !== tableName);
      }

      const updated = { ...rest, columns: updatedColumns };
      return dataSelection.map((s, i) => (i === existingIndex ? updated : s));
    })();

    setValue('dataSelection', nextSelection, { shouldDirty: true });
  };

  const toggleTableSelection = (tableName: string) => {
    const existingIndex = dataSelection.findIndex((curr) => curr.name === tableName);
    const table = data.find((t) => t.name === tableName);

    if (!table) return;

    const isFullySelected = isTableSelected(tableName) === true;

    const nextSelection = (() => {
      if (isFullySelected) {
        return dataSelection.filter((_, i) => i !== existingIndex);
      }

      const allColumns = table.columns.map((column) => ({
        name: column.name,
        data_type: column.data_type,
        sample_values: column.sample_values || undefined,
        description: column.description || '',
        synonyms: column.synonyms || undefined,
      }));

      if (existingIndex === -1) {
        return [...dataSelection, { name: tableName, columns: allColumns }];
      }

      const { ...rest } = dataSelection[existingIndex];
      const updated = { ...rest, columns: allColumns };
      return dataSelection.map((s, i) => (i === existingIndex ? updated : s));
    })();

    setValue('dataSelection', nextSelection, { shouldDirty: true });
  };

  const onSelectAll = () => {
    setValue('dataSelection', tablesToDataSelection({ tables: data }), { shouldDirty: true });
  };

  const onDeselectAll = () => {
    setValue('dataSelection', [], { shouldDirty: true });
  };

  return (
    <Box pb="$32">
      <Box display="flex" alignItems="center" mt="$16" mb="$8">
        <Typography variant="body-medium-loose" fontWeight="medium">
          Select data
        </Typography>
        <Box display="flex" gap="$4" ml="auto">
          <Button variant="ghost-subtle" onClick={onSelectAll}>
            Select All
          </Button>
          <Button variant="ghost-subtle" onClick={onDeselectAll}>
            Deselect All
          </Button>
        </Box>
      </Box>
      <TreeList>
        {data.map((table) => {
          const selecteditems = dataSelection.find((selection) => selection.name === table.name)?.columns.length || 0;
          const Icon = fileRefId ? IconDbSpreadsheet : IconDbDatabase;
          return (
            <TreeList.Checkbox
              key={table.name}
              open={selecteditems > 0 && data.length === 1}
              checked={isTableSelected(table.name) !== false}
              indeterminate={isTableSelected(table.name) === 'partial'}
              onChange={() => toggleTableSelection(table.name)}
              label={
                <>
                  {table.name}{' '}
                  <Typography color="content.subtle.light">
                    ({selecteditems}/{table.columns.length})
                  </Typography>
                </>
              }
              icon={Icon}
            >
              {table.columns.map((column) => (
                <TreeList.Checkbox
                  key={`${table.name}.${column.name}`}
                  checked={isColumnSelected(table.name, column.name)}
                  onChange={() => toggleColumnSelection(table.name, column)}
                  label={column.name || '-'}
                  icon={IconDbColumn}
                />
              ))}
            </TreeList.Checkbox>
          );
        })}
      </TreeList>
    </Box>
  );
};

import { FC, useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type MouseEvent } from 'react';
import { Box, Button, Checkbox, Typography } from '@sema4ai/components';
import {
  IconChevronDown,
  IconChevronRight,
  IconDbColumn,
  IconDbDatabase,
  IconDbSpreadsheet,
  IconLoading,
} from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';
import { styled } from '@sema4ai/theme';

import { useColumnSamplesQuery, useTableProfileQuery } from '~/queries/dataConnections';
import type { ServerResponse } from '@sema4ai/agent-server-interface';
import { DataConnectionFormSchema, tablesToDataSelection } from './form';

type InspectDataConnectionResponse = ServerResponse<'post', '/api/v2/data-connections/{connection_id}/inspect'>;
type TableInfo = InspectDataConnectionResponse['tables'][number];
type ColumnInfo = TableInfo['columns'][number];

const ClickableRow = styled(Box)`
  cursor: pointer;

  &:hover {
    background-color: ${({ theme }) => theme.colors.background.subtle.light.color};
  }
`;

const ExpandToggle = styled(Box)`
  cursor: pointer;
  display: flex;
  align-items: center;
`;

const formatRowCount = (count: number | null | undefined): string => {
  if (count === null || count === undefined) return '';
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M rows`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K rows`;
  return `${count} rows`;
};

const formatSampleValues = (samples: unknown[] | null | undefined): string => {
  if (!samples || samples.length === 0) return '';
  const displaySamples = samples.slice(0, 3).map((sample) => {
    if (sample === null) return 'null';
    if (typeof sample === 'string') {
      const trimmed = sample.trim();
      return trimmed.length > 15 ? `${trimmed.slice(0, 15)}…` : trimmed;
    }
    const str = String(sample);
    return str.length > 15 ? `${str.slice(0, 15)}…` : str;
  });
  const suffix = samples.length > 3 ? ' …' : '';
  return displaySamples.join(' | ') + suffix;
};

type ColumnRowProps = {
  column: ColumnInfo;
  table: TableInfo;
  dataConnectionId: string | undefined;
  isSelected: boolean;
  onToggle: (shouldSelect: boolean) => void;
};

const ColumnRow: FC<ColumnRowProps> = ({ column, table, dataConnectionId, isSelected, onToggle }) => {
  const needsSamples = !!dataConnectionId && (column.sample_values === null || column.sample_values === undefined);
  const { data: samplesData, isLoading } = useColumnSamplesQuery(
    {
      connectionId: dataConnectionId || '',
      tableName: table.name,
      columnName: column.name,
      database: table.database ?? undefined,
      schema: table.schema ?? undefined,
    },
    { enabled: !!needsSamples },
  );

  const displaySamples = samplesData?.sample_values ?? column.sample_values;
  const rawDataType = samplesData?.data_type ?? column.data_type;
  const displayDataType = rawDataType?.startsWith('!') ? rawDataType.slice(1) : rawDataType;
  const sampleText = formatSampleValues(displaySamples);

  const handleCheckboxChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      onToggle(event.target.checked);
    },
    [onToggle],
  );

  const handleRowToggle = useCallback(() => {
    onToggle(!isSelected);
  }, [isSelected, onToggle]);

  const Icon = isLoading ? IconLoading : IconDbColumn;

  return (
    <ClickableRow display="flex" alignItems="flex-start" gap="$8" py="$8" pl="$24" pr="$16" onClick={handleRowToggle}>
      <Box
        onClick={(event: MouseEvent) => {
          event.stopPropagation();
          // Manually toggle since onChange might not be firing
          onToggle(!isSelected);
        }}
      >
        <Checkbox checked={isSelected} aria-label={`Select column ${column.name}`} onChange={handleCheckboxChange} />
      </Box>
      <Box color="content.subtle.light" pt="$2">
        <Icon size={16} />
      </Box>
      <Box display="flex" flexDirection="column" gap="$2" flex={1}>
        <Box display="flex" alignItems="baseline" gap="$8">
          <Typography variant="body-medium">{column.name || '-'}</Typography>
          <Typography variant="body-small" color="content.subtle.light">
            {displayDataType}
          </Typography>
        </Box>
        {(() => {
          if (isLoading) {
            return (
              <Typography variant="body-small" color="content.subtle.light" fontStyle="italic">
                Loading samples…
              </Typography>
            );
          }
          if (sampleText) {
            return (
              <Typography variant="body-small" color="content.subtle.light" fontFamily="mono">
                {sampleText}
              </Typography>
            );
          }
          return null;
        })()}
      </Box>
    </ClickableRow>
  );
};

type TableRowProps = {
  table: TableInfo;
  dataConnectionId: string | undefined;
  fileRefId: string | undefined;
  isChecked: boolean;
  isIndeterminate: boolean;
  selectedCount: number;
  defaultOpen: boolean;
  onToggle: (shouldSelect: boolean) => void;
  onColumnToggle: (column: ColumnInfo, shouldSelect: boolean) => void;
  isColumnSelected: (columnName: string) => boolean;
  onExpand: (tableName: string) => void;
};

const TableRow: FC<TableRowProps> = ({
  table,
  dataConnectionId,
  fileRefId,
  isChecked,
  isIndeterminate,
  selectedCount,
  defaultOpen,
  onToggle,
  onColumnToggle,
  isColumnSelected,
  onExpand,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultOpen);
  const { data: profileData, isLoading: isLoadingProfile } = useTableProfileQuery(
    {
      connectionId: dataConnectionId || '',
      tableName: table.name,
      database: table.database ?? undefined,
      schema: table.schema ?? undefined,
    },
    { enabled: !!dataConnectionId },
  );

  const rowCountText = formatRowCount(profileData?.row_count);
  const Icon = fileRefId ? IconDbSpreadsheet : IconDbDatabase;

  const handleTableToggle = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      onToggle(event.target.checked);
    },
    [onToggle],
  );

  const handleExpandToggle = useCallback(() => {
    onExpand(table.name);
    setIsExpanded((prev) => !prev);
  }, [onExpand, table.name]);

  const ExpandIcon = isExpanded ? IconChevronDown : IconChevronRight;

  return (
    <>
      <ClickableRow display="flex" alignItems="center" gap="$8" py="$8" px="$8">
        <ExpandToggle onClick={handleExpandToggle}>
          <ExpandIcon size={16} />
        </ExpandToggle>
        <Box
          onClick={(event: MouseEvent) => {
            event.stopPropagation();
            onToggle(!isChecked);
          }}
        >
          <Checkbox
            checked={isChecked}
            indeterminate={isIndeterminate}
            aria-label={`Select table ${table.name}`}
            onChange={handleTableToggle}
          />
        </Box>
        <Box color="content.subtle.light">
          <Icon size={16} />
        </Box>
        <Box display="flex" alignItems="baseline" gap="$8" flex={1} onClick={handleExpandToggle}>
          <Typography variant="body-medium">{table.name}</Typography>
          <Typography variant="body-small" color="content.subtle.light">
            ({selectedCount}/{table.columns.length})
          </Typography>
          {(() => {
            if (isLoadingProfile) {
              return (
                <Typography variant="body-small" color="content.subtle.light" fontStyle="italic">
                  Loading…
                </Typography>
              );
            }
            if (rowCountText) {
              return (
                <Typography variant="body-small" color="content.subtle.light">
                  • {rowCountText}
                </Typography>
              );
            }
            return null;
          })()}
        </Box>
      </ClickableRow>
      {isExpanded && (
        <Box pl="$32">
          {table.columns.map((column) => (
            <ColumnRow
              key={`${table.name}.${column.name}`}
              column={column}
              table={table}
              dataConnectionId={dataConnectionId}
              isSelected={isColumnSelected(column.name)}
              onToggle={(shouldSelect) => onColumnToggle(column, shouldSelect)}
            />
          ))}
        </Box>
      )}
    </>
  );
};

export const DataSelector: FC<{ data: TableInfo[]; dataConnectionId?: string }> = ({ data, dataConnectionId }) => {
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const { dataSelection = [], fileRefId } = watch();
  const [stableSelection, setStableSelection] = useState<DataConnectionFormSchema['dataSelection']>(dataSelection);
  const lastActionRef = useRef<'init' | 'toggle' | 'selectAll' | 'clearAll'>('init');
  const lastExpandAtRef = useRef(0);

  useEffect(() => {
    if (dataSelection.length === 0 && stableSelection.length > 0 && lastActionRef.current !== 'clearAll') {
      setValue('dataSelection', stableSelection, { shouldDirty: false });
      return;
    }
    setStableSelection(dataSelection);
  }, [dataSelection, setValue]);

  const dataSelectionByTable = useMemo(() => {
    return new Map(stableSelection.map((selection) => [selection.name, selection]));
  }, [stableSelection]);

  const isColumnSelected = useCallback(
    (tableName: string, columnName: string): boolean => {
      const tableSelection = dataSelectionByTable.get(tableName);
      return !!tableSelection && tableSelection.columns.some((column) => column.name === columnName);
    },
    [dataSelectionByTable],
  );

  const isTableSelected = useCallback(
    (tableName: string): boolean | 'partial' => {
      const tableSelection = dataSelectionByTable.get(tableName);
      if (!tableSelection) {
        return false;
      }

      if (tableSelection.columns.length === 0) {
        return false;
      }

      const selectedColumns = data
        .find((curr) => curr.name === tableName)
        ?.columns.filter((col) => tableSelection.columns.some((column) => column.name === col.name));

      return selectedColumns?.length === data.find((curr) => curr.name === tableName)?.columns.length
        ? true
        : 'partial';
    },
    [data, dataSelectionByTable],
  );

  const buildColumnDefinition = (column: ColumnInfo) => ({
    name: column.name,
    data_type: column.data_type,
    sample_values: column.sample_values ?? undefined,
    description: column.description ?? '',
    synonyms: column.synonyms ?? undefined,
  });

  const handleColumnToggle = useCallback(
    (tableName: string, column: ColumnInfo, shouldSelect: boolean) => {
      const columnDefinition = buildColumnDefinition(column);
      const nextSelection = (() => {
        const currentSelection = stableSelection;
        const existingIndex = currentSelection.findIndex((curr) => curr.name === tableName);

        if (existingIndex === -1) {
          return shouldSelect
            ? [...currentSelection, { name: tableName, columns: [columnDefinition] }]
            : currentSelection;
        }

        const { columns, ...rest } = currentSelection[existingIndex];

        const alreadySelected = columns.some((curr) => curr.name === column.name);
        const updatedColumns = (() => {
          if (!shouldSelect) {
            return columns.filter((col) => col.name !== column.name);
          }
          if (alreadySelected) {
            return columns;
          }
          return [...columns, columnDefinition];
        })();

        if (updatedColumns.length === 0) {
          return currentSelection.filter((selection) => selection.name !== tableName);
        }

        const updated = { ...rest, columns: updatedColumns };
        return currentSelection.map((selection, index) => (index === existingIndex ? updated : selection));
      })();

      lastActionRef.current = 'toggle';
      setStableSelection(nextSelection);
      setValue('dataSelection', nextSelection, { shouldDirty: true });
    },
    [setValue, stableSelection],
  );

  const handleTableSelectionChange = useCallback(
    (tableName: string, shouldSelect: boolean) => {
      const currentSelection = stableSelection;
      const existingIndex = currentSelection.findIndex((curr) => curr.name === tableName);
      const table = data.find((curr) => curr.name === tableName);

      if (!table) return;

      const nextSelection = (() => {
        if (!shouldSelect) {
          return currentSelection.filter((_, index) => index !== existingIndex);
        }

        const allColumns = table.columns.map((column) => ({
          name: column.name,
          data_type: column.data_type,
          sample_values: column.sample_values ?? undefined,
          description: column.description ?? '',
          synonyms: column.synonyms ?? undefined,
        }));

        if (existingIndex === -1) {
          return [...currentSelection, { name: tableName, columns: allColumns }];
        }

        const { ...rest } = currentSelection[existingIndex];
        const updated = { ...rest, columns: allColumns };
        return currentSelection.map((selection, index) => (index === existingIndex ? updated : selection));
      })();

      lastActionRef.current = 'toggle';
      setStableSelection(nextSelection);
      setValue('dataSelection', nextSelection, { shouldDirty: true });
    },
    [data, setValue, stableSelection],
  );

  const handleSelectAll = useCallback(() => {
    const elapsed = Date.now() - lastExpandAtRef.current;
    if (elapsed < 200) {
      return;
    }
    const nextSelection = tablesToDataSelection({ tables: data });
    lastActionRef.current = 'selectAll';
    setStableSelection(nextSelection);
    setValue('dataSelection', nextSelection, { shouldDirty: true });
  }, [data, setValue]);

  const handleDeselectAll = useCallback(() => {
    const elapsed = Date.now() - lastExpandAtRef.current;
    if (elapsed < 200) {
      return;
    }
    lastActionRef.current = 'clearAll';
    setStableSelection([]);
    setValue('dataSelection', [], { shouldDirty: true });
  }, [setValue]);

  const handleTableExpand = useCallback(() => {
    lastExpandAtRef.current = Date.now();
  }, []);

  return (
    <Box pb="$32">
      <Box display="flex" alignItems="center" mt="$16" mb="$8">
        <Typography variant="body-medium-loose" fontWeight="medium">
          Select data
        </Typography>
        <Box display="flex" gap="$4" ml="auto">
          <Button variant="ghost-subtle" type="button" onPointerUp={handleSelectAll}>
            Select All
          </Button>
          <Button variant="ghost-subtle" type="button" onPointerUp={handleDeselectAll}>
            Deselect All
          </Button>
        </Box>
      </Box>
      <Box>
        {data.map((table) => {
          const selectedColumnCount =
            stableSelection.find((selection) => selection.name === table.name)?.columns.length || 0;
          const defaultOpen = selectedColumnCount > 0 && data.length === 1;

          return (
            <TableRow
              key={table.name}
              table={table}
              dataConnectionId={dataConnectionId}
              fileRefId={fileRefId}
              isChecked={isTableSelected(table.name) !== false}
              isIndeterminate={isTableSelected(table.name) === 'partial'}
              selectedCount={selectedColumnCount}
              defaultOpen={defaultOpen}
              onToggle={(shouldSelect) => handleTableSelectionChange(table.name, shouldSelect)}
              onColumnToggle={(column, shouldSelect) => handleColumnToggle(table.name, column, shouldSelect)}
              isColumnSelected={(columnName) => isColumnSelected(table.name, columnName)}
              onExpand={handleTableExpand}
            />
          );
        })}
      </Box>
    </Box>
  );
};

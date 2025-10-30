import {
  Box,
  Typography,
  Column,
  Tooltip,
  Input,
} from '@sema4ai/components';
import { IconSparkles2, IconInformation } from '@sema4ai/icons';
import { FC, useEffect, useMemo, useCallback, useState } from 'react';
import { LayoutFieldRow, LayoutTableRow } from '../types';
import { DataModelFieldRowItem } from './common/DataModelFieldRowItem';
import { StepDataTable } from './common/StepDataTable';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import { ProcessingLoadingState } from './common/ProcessingLoadingState';

interface StepDataModelProps {
  isReadOnly?: boolean;
  isProcessing?: boolean;
  processingStep?: string;
}

export const StepDataModel: FC<StepDataModelProps> = ({
  isReadOnly = false,
  isProcessing = false,
  processingStep,
}) => {

  const layoutFields = useDocumentIntelligenceStore((state) => state.layoutFields);
  const layoutTables = useDocumentIntelligenceStore((state) => state.layoutTables);
  const updateField = useDocumentIntelligenceStore((state) => state.updateField);
  const updateTableField = useDocumentIntelligenceStore((state) => state.updateTableField);

  const [cachedFields, setCachedFields] = useState<LayoutFieldRow[]>(layoutFields);
  const [cachedTables, setCachedTables] = useState<LayoutTableRow[]>(layoutTables);

  useEffect(() => {
    setCachedFields(layoutFields);
  }, [layoutFields]);

  useEffect(() => {
    setCachedTables(layoutTables);
  }, [layoutTables]);

  const fieldColumns: Column[] = useMemo(
    () => [
      { id: 'field', title: 'Field', sortable: true, width: 120 },
      { id: 'exampleValue', title: 'Example Value', sortable: true, width: 150 },
      { id: 'dataType', title: 'Data Type', sortable: true, width: 100 },
      { id: 'required', title: 'Required', sortable: true, width: 80 },
      { id: 'context', title: 'Context', sortable: true, width: 200 },
    ],
    [],
  );

  const headerText = useMemo(() => {
    if (isProcessing) {
      return 'Creating Data Model';
    }
    return 'Information inferred below. Edit values directly below, via Agent chat or annotations.';
  }, [isProcessing]);

  const header = useMemo(
    () => (
      <Box display="flex" gap="$8" alignItems="center" marginBottom="$12">
        <IconSparkles2 color="content.subtle.light" />
        <Typography fontSize="$12" color="content.subtle.light">
          {headerText}
        </Typography>
      </Box>
    ),
    [headerText],
  );

  const handleFieldContextChange = useCallback(
    (fieldId: string, instructions: string | undefined) => {
      const updates = { description: instructions };
      updateField(fieldId, updates);
    },
    [updateField],
  );

  const handleFieldTypeChange = useCallback(
    (fieldId: string, fieldType: string) => {
      const updates = { type: fieldType };
      updateField(fieldId, updates);
    },
    [updateField],
  );

  const handleFieldRequiredChange = useCallback(
    (fieldId: string, required: boolean) => {
      const updates = { required };
      updateField(fieldId, updates);
    },
    [updateField],
  );

  const tableRowProps = useCallback(
    (table: LayoutTableRow) => ({
      onFieldContextChange: (column: string, instructions: string | undefined) => {
        const newTable = {
          ...table,
          columnsMeta: {
            ...table.columnsMeta,
            [column]: { ...table.columnsMeta[column], description: instructions || '' },
          },
        };
        updateTableField(table.name, newTable);
      },
      onFieldTypeChange: (column: string, fieldType: string) => {
        const newTable = {
          ...table,
          columnsMeta: {
            ...table.columnsMeta,
            [column]: { ...table.columnsMeta[column], type: fieldType || 'String' },
          },
        };
        updateTableField(table.name, newTable);
      },
      onFieldRequiredChange: (column: string, required: boolean) => {
        const newTable = {
          ...table,
          columnsMeta: { ...table.columnsMeta, [column]: { ...table.columnsMeta[column], required } },
        };
        updateTableField(table.name, newTable);
      },
      isReadOnly,
    }),
    [updateTableField, isReadOnly],
  );

  if (isProcessing) {
    return <ProcessingLoadingState processingStep={processingStep} title="Creating Data Model" />;
  }

  if (cachedFields.length === 0 && cachedTables.length === 0) {
    return (
      <Box style={{ height: '100%' }}>
        <Typography fontSize="$16" fontWeight="medium" marginBottom="$16">
          Data Model Configuration
        </Typography>

        <Box flex="1" display="flex" alignItems="center" justifyContent="center">
          <Typography color="content.subtle">No data model available for configuration</Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column">
      {header}

      {/* Fields Section */}
      {cachedFields.length > 0 && (
        <>
          <Box marginTop="$16" display="flex" alignItems="center" gap="$8" marginBottom="$12">
            <Typography fontSize="$16" fontWeight="bold">
              Fields
            </Typography>
            <Tooltip
              text={
                <Box display="flex" flexDirection="column" gap="$4">
                  <Typography>Fields are the data that will be extracted from the document.</Typography>
                  <Typography>You can edit the field types, requirements, and descriptions below.</Typography>
                </Box>
              }
            >
              <IconInformation color="content.subtle" size={24} />
            </Tooltip>
          </Box>

          <StepDataTable
            columns={fieldColumns}
            data={cachedFields}
            row={DataModelFieldRowItem}
            rowProps={{
              onFieldContextChange: handleFieldContextChange,
              onFieldTypeChange: handleFieldTypeChange,
              onFieldRequiredChange: handleFieldRequiredChange,
              isReadOnly,
            }}
            layout="auto"
            rowCount="all"
            selectable={false}
          />
        </>
      )}

      {/* Tables Section */}
      {cachedTables.length > 0 && (
        <Box marginTop="$24" display="flex" flexDirection="column">
          <Box display="flex" alignItems="center" justifyContent="space-between" marginBottom="$12">
            <Box display="flex" alignItems="center" gap="$8">
              <Typography fontSize="$16" fontWeight="bold">
                Tables
              </Typography>
              <Tooltip
                text={
                  <Box display="flex" flexDirection="column" gap="$4">
                    <Typography>Tables are the data that will be extracted from the document.</Typography>
                    <Typography>You can edit the table columns, types, requirements, and descriptions below.</Typography>
                  </Box>
                }
              >
                <IconInformation color="content.subtle" size={24} />
              </Tooltip>
            </Box>
          </Box>

          {/* Render each table with its data */}
          {cachedTables.map((table) => {
            const columnsData: LayoutFieldRow[] = Object.entries(table.columnsMeta).map(([column, meta]) => {
              const metaObj = meta as { type: string; required: boolean; description: string };
              return {
                id: column,
                name: column,
                type: metaObj.type,
                required: metaObj.required,
                description: metaObj.description,
                value: table.data?.[0]?.[column] || '',
              };
            });

            return (
              <Box key={table.id} marginBottom="$24">
                {/* Table Name Header */}
                <Box display="flex" flexDirection="column" marginBottom="$16" style={{ width: '100%' }}>
                  <Typography fontSize="$16" fontWeight="bold">
                    {table.name}
                  </Typography>
                  <Box alignItems="center" gap="$8" marginTop="$8" style={{ width: '100%' }}>
                    <Input
                      label=""
                      value={table.description || ''}
                      onChange={(e) => {
                        const newTable = { ...table, description: e.target.value };
                        updateTableField(table.name, newTable);
                      }}
                      placeholder="Table description"
                      disabled={isReadOnly}
                    />
                  </Box>
                </Box>

                {/* Table Columns */}
                {table.columnsMeta && (
                  <StepDataTable
                    columns={fieldColumns}
                    data={columnsData}
                    row={DataModelFieldRowItem}
                    rowProps={tableRowProps(table)}
                    layout="auto"
                    rowCount="all"
                    selectable={false}
                  />
                )}
              </Box>
            );
          })}
        </Box>
      )}
    </Box>
  );
};

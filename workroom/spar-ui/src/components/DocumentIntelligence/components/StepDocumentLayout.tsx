import {
  Box,
  Button,
  Form,
  Input,
  Typography,
  Column,
  Tooltip,
  Progress,
} from '@sema4ai/components';
import { IconSparkles2, IconPlus, IconCursorText, IconInformation, IconPencil } from '@sema4ai/icons';
import { ChangeEvent, FC, useCallback, useMemo, useState, useEffect, useRef } from 'react';

import { LayoutFieldRow, getTableColumns, FieldRowProps, DocumentData } from '../types';
import { StepDataTable, StepDataDisplayTable } from './common/StepDataTable';
import { TableDataRowItem } from './common/TableDataRowItem';
import { FieldRowItem } from './common/FieldRowItem';
import Collapsible from './common/Collapsible';
import { StyledEditButton } from './common/styles';
import { SpecialHandlingMenu } from './common/SpecialHandlingMenu';
import { SpecialHandlingInstructions } from './common/SpecialHandlingInstructions';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import { useDocumentLayoutFlow } from '../hooks/useDocumentIntelligenceFlows';

interface StepDocumentLayoutProps {
  documentData: DocumentData;
  isReadOnly?: boolean;
  isProcessing?: boolean;
  processingStep?: string;
}

export const StepDocumentLayout: FC<StepDocumentLayoutProps> = ({
  documentData,
  isReadOnly = false,
  isProcessing = false,
  processingStep
}) => {
  const { fileRef, threadId, agentId, flowType } = documentData;

  const {
    currentFlowType,
    layoutFields,
    layoutTables,
    selectedFields,
    selectedTableColumns,
    documentLayout,
    updateField,
    updateTableField,
    addField,
    removeField,
    setDocumentLayout,
  } = useDocumentIntelligenceStore();

  const effectiveFlowType = currentFlowType || flowType;

  const { executeDocumentLayoutFlow, isLoading: flowLoading } = useDocumentLayoutFlow();
  const [busy, setBusy] = useState(false);
  const [cachedSelectedFields, setCachedSelectedFields] = useState<string[]>([]);
  const [cachedSelectedTableColumns, setCachedSelectedTableColumns] = useState<Record<string, string[]>>({});

  const flowExecutedRef = useRef(false);

  // Initialize flow when component mounts (only once)
  useEffect(() => {
    // Only run the flow for parse_current_document flow and if it hasn't been executed yet
    if (fileRef && threadId && agentId && !isProcessing && !flowLoading && !flowExecutedRef.current && effectiveFlowType === 'parse_current_document') {
      flowExecutedRef.current = true;
      executeDocumentLayoutFlow({
        fileRef,
        threadId,
        agentId,
        dataModelName: documentData.dataModelName,
        flowType: effectiveFlowType,
      }).catch(() => {
        flowExecutedRef.current = false;
      });
    }
  }, [fileRef, threadId, agentId, effectiveFlowType, documentData.dataModelName, isProcessing, flowLoading]);

  // Sync local selection state with store
  useEffect(() => {
    setCachedSelectedFields(layoutFields.filter((_, index) => selectedFields.includes(index)).map(field => field.id));
  }, [layoutFields, selectedFields]);

  useEffect(() => {
    const tableSelections: Record<string, string[]> = {};
    Object.entries(selectedTableColumns).forEach(([tableName, indices]) => {
      const table = layoutTables.find(t => t.name === tableName);
      if (table) {
        tableSelections[tableName] = indices.map(index => table.columns[index]).filter(Boolean);
      }
    });
    setCachedSelectedTableColumns(tableSelections);
  }, [layoutTables, selectedTableColumns]);


  const handleSaveFieldInstructions = useCallback(
    (fieldId: string, instructions: string) => {
      updateField(fieldId, { layout_description: instructions });
    },
    [updateField],
  );

  const handleSaveTableSpecialHandling = useCallback(
    (tableName: string, instructions: string) => {

      const currentTable = layoutTables.find(table => table.name === tableName);
      if (!currentTable) return;

      // Update the table's layout_description
      const updatedTable = {
        ...currentTable,
        layout_description: instructions,
      };

      updateTableField(tableName, updatedTable);
    },
    [layoutTables, updateTableField],
  );

  const handleSaveTableColumnInstructions = useCallback(
    (tableName: string, columnName: string, instructions: string) => {

      const currentTable = layoutTables.find(table => table.name === tableName);
      if (!currentTable) return;

      // Update the specific column's layout_description
      const updatedTable = {
        ...currentTable,
        columnsMeta: {
          ...currentTable.columnsMeta,
          [columnName]: {
            ...currentTable.columnsMeta[columnName],
            layout_description: instructions,
          },
        },
      };

      updateTableField(tableName, updatedTable);
    },
    [layoutTables, updateTableField],
  );

  // Handle deleting a table column
  const handleDeleteTableColumn = useCallback(
    (tableName: string, columnName: string) => {
      const currentTable = layoutTables.find(table => table.name === tableName);
      if (!currentTable) return;

      // Remove column from columns array
      const updatedColumns = currentTable.columns.filter(col => col !== columnName);

      // Remove column from columnsMeta
      const updatedColumnsMeta = Object.fromEntries(
        Object.entries(currentTable.columnsMeta).filter(([col]) => col !== columnName)
      );

      updateTableField(tableName, {
        ...currentTable,
        columns: updatedColumns,
        columnsMeta: updatedColumnsMeta,
      });
    },
    [layoutTables, updateTableField]
  );

  // Handle updating column name
  const handleUpdateColumnName = useCallback(
    (tableName: string, oldColumnName: string, newColumnName: string) => {
      const currentTable = layoutTables.find(table => table.name === tableName);
      if (!currentTable) return;

      // Update columns array - maintain order
      const updatedColumns = currentTable.columns.map(col =>
        col === oldColumnName ? newColumnName : col
      );

      // Update columnsMeta - preserve metadata but with new key
      const updatedColumnsMeta = { ...currentTable.columnsMeta };
      if (updatedColumnsMeta[oldColumnName]) {
        updatedColumnsMeta[newColumnName] = updatedColumnsMeta[oldColumnName];
        delete updatedColumnsMeta[oldColumnName];
      }

      updateTableField(tableName, {
        ...currentTable,
        columns: updatedColumns,
        columnsMeta: updatedColumnsMeta,
      });
    },
    [layoutTables, updateTableField]
  );

  // Handle updating table name
  const handleUpdateTableName = useCallback(
    (oldTableName: string, newTableName: string) => {
      const currentTable = layoutTables.find(table => table.name === oldTableName);
      if (!currentTable) return;

      // Update the table with the new name
      updateTableField(oldTableName, {
        ...currentTable,
        name: newTableName,
      });
    },
    [layoutTables, updateTableField]
  );

  const handleAddField = useCallback(() => {
    const newField = addField({
      type: 'string',
      required: true,
      name: '',
      value: '',
    });
    setCachedSelectedFields(prev => [...prev, newField.id]);
  }, [addField]);

  const handleDeleteField = useCallback(
    (fieldId: string) => {
      removeField(fieldId);
      setCachedSelectedFields(prev => prev.filter(id => id !== fieldId));
    },
    [removeField],
  );

  const handleChangeFieldName = useCallback(
    (id: string, key: 'name' | 'value') => (e: ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value;
      updateField(id, { [key]: newValue });
    },
    [updateField],
  );

  const onSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setBusy(true);
      window.setTimeout(() => setBusy(false), 800);
    },
    [setBusy],
  );

  const viewHeader = useMemo(
    () => (
      <Box display="flex" alignItems="center" gap="$8" marginBottom="$12">
        <IconSparkles2 color="content.subtle.light" />
        <Typography fontSize="$12" color="content.subtle.light">
          Fields and tables inferred below. Edit values directly below, via Agent chat or annotations.
        </Typography>
      </Box>
    ),
    [],
  );

  const fieldsColumns: Column[] = useMemo(
    () =>
      [
        { id: 'field', title: 'Field', sortable: true, width: 200 },
        { id: 'value', title: 'Value', sortable: true, width: 250 },
        isReadOnly
          ? undefined
          : { id: 'annotate', title: 'Annotate', sortable: false, className: '!text-left', width: 100 },
        isReadOnly ? undefined : { id: 'delete', title: 'Delete', sortable: false, className: '!text-left', width: 80 },
      ].filter((column) => column !== undefined),
    [isReadOnly],
  );

  const tableEditableColumns: Column[] = useMemo(
    () =>
      [
        { id: 'field', title: 'Column', sortable: true, width: 200 },
        { id: 'value', title: 'ExampleValue', sortable: true, width: 250 },
        isReadOnly
          ? undefined
          : { id: 'annotate', title: 'Annotate', sortable: false, className: '!text-left', width: 100 },
        isReadOnly ? undefined : { id: 'delete', title: 'Delete', sortable: false, className: '!text-left', width: 80 },
      ].filter((column) => column !== undefined),
    [isReadOnly],
  );

  const fieldsRowProps = useMemo<FieldRowProps>(
    () => ({
      onChange: handleChangeFieldName,
      onSaveSpecialHandling: handleSaveFieldInstructions,
      onDelete: handleDeleteField,
      showAnnotateButtons: !isReadOnly,
      readOnlyFields: isReadOnly,
      label: 'Field',
    }),
    [handleChangeFieldName, handleSaveFieldInstructions, handleDeleteField, isReadOnly],
  );

  // Show loading state
  if (flowLoading || isProcessing) {
    return (
      <Box style={{ height: '100%' }}>
        <Box display="flex" alignItems="center" gap="$8" marginBottom="$8">
          <IconSparkles2 color="content.subtle.light" />
          <Typography fontSize="$16" fontWeight="medium" color="content.subtle.light">
            {processingStep || 'Processing document...'}
          </Typography>
        </Box>

        <Box display="flex" gap="$8">
          <Progress id="flim-flam" />
        </Box>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column">
      {viewHeader}

      <SpecialHandlingInstructions
        step="document_layout"
        objectPrompt={documentLayout?.prompt}
        disabled={isReadOnly}
        onUpdate={(prompt) => {
          if (documentLayout) {
            setDocumentLayout({ ...documentLayout, prompt });
          } else {
            setDocumentLayout({ prompt });
          }
        }}
      />

      <Box marginTop="$16" display="flex" alignItems="center" gap="$8" marginBottom="$12">
        <Typography fontSize="$16" fontWeight="bold">
          Fields
        </Typography>
        <Tooltip
          text={
            <Box display="flex" flexDirection="column" gap="$4">
              <Typography>Fields are the data that will be extracted from the document.</Typography>
              <Typography>You can add, edit and select the wanted fields below.</Typography>
            </Box>
          }
        >
          <IconInformation color="content.subtle" size={24} />
        </Tooltip>
      </Box>

      <Form busy={busy} onSubmit={onSubmit} gap="$12" display="flex" flexDirection="column">
        <StepDataTable
          selectable={!isReadOnly}
          selected={cachedSelectedFields}
          onSelect={setCachedSelectedFields}
          columns={fieldsColumns}
          data={layoutFields}
          row={FieldRowItem}
          rowProps={fieldsRowProps}
          layout="auto"
          rowCount="all"
        />

        {!isReadOnly && (
          <Box marginTop="$8" display="flex" gap="$8">
            <Button
              type="button"
              icon={IconPlus}
              variant="ghost"
              onClick={handleAddField}
              round
              style={{
                border: '1px solid #DADEE3',
                backgroundColor: 'white',
              }}
            >
              Add Field
            </Button>
          </Box>
        )}
      </Form>

      {/* Tables Section */}
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
                  <Typography>You can edit and select the wanted table columns below.</Typography>
                </Box>
              }
            >
              <IconInformation color="content.subtle" size={24} />
            </Tooltip>
          </Box>
        </Box>

        {/* Render each table with its data */}
        {layoutTables.map((table) => {
          const columns = getTableColumns(table);
          const columnsData: LayoutFieldRow[] = Object.entries(table.columnsMeta).map(([column, meta]) => ({
            id: column,
            name: column,
            type: meta.type,
            required: meta.required,
            description: meta.description,
            layout_description: meta.layout_description,
            value: table.data?.[0]?.[column] || '',
          }));

          const rowProps: FieldRowProps = {
            onChange: () => () => {
              // This will be handled by the local state in FieldRowItem
            },
            onBlur: (columnId: string, key: 'name' | 'value') => (e: React.FocusEvent<HTMLInputElement>) => {
              if (key === 'name') {
                const newName = e.target.value;
                handleUpdateColumnName(table.name, columnId, newName);
              }
            },
            onKeyDown: (columnId: string, key: 'name' | 'value') => (e: React.KeyboardEvent<HTMLInputElement>) => {
              if (key === 'name') {
                if (e.key === 'Enter') {
                  const newName = e.currentTarget.value;
                  handleUpdateColumnName(table.name, columnId, newName);
                }
              }
            },

            onSaveSpecialHandling: (column: string, instructions: string) => {
              handleSaveTableColumnInstructions(table.name, column, instructions);
            },
            onDelete: (columnId: string) => {
              handleDeleteTableColumn(table.name, columnId);
            },
            showAnnotateButtons: !isReadOnly,
            readOnlyFields: isReadOnly,
            label: 'Column',
          };

          return (
            <Box key={table.id} marginBottom="$24">
              {/* Table Name Header */}
              <Box display="flex" alignItems="center" justifyContent="space-between" marginBottom="$16">
                <Box
                  display="flex"
                  alignItems="center"
                  justifyContent="space-between"
                  gap="$8"
                  style={{ flex: 1, width: '100%' }}
                >
                  <Box style={{ flex: 1, width: '100%' }}>
                    {isReadOnly ? (
                      <Typography fontSize="$16" fontWeight="medium">
                        {table.name}
                      </Typography>
                    ) : (
                      <Input
                        aria-label="Table name"
                        placeholder="Table name"
                        value={table.name}
                        onChange={(e) => handleUpdateTableName(table.name, e.target.value)}
                        style={{
                          width: '100%',
                        }}
                      />
                    )}
                  </Box>
                  {!isReadOnly && (
                    <SpecialHandlingMenu
                      fieldId={table.name}
                      fieldName={table.name}
                      currentInstructions={table.layout_description || ''}
                      onSave={(fieldId: string, instructions: string) => {
                        handleSaveTableSpecialHandling(fieldId, instructions);
                      }}
                      onCancel={() => {}}
                      label="Table"
                      trigger={
                        <StyledEditButton
                          aria-label="Table Special Handling"
                          size="medium"
                          variant="outline"
                          icon={IconCursorText}
                          iconAfter={IconPencil}
                          round
                        />
                      }
                    />
                  )}
                </Box>
              </Box>

              {/* Table Columns */}
              {table.columnsMeta && (
                <Collapsible
                  header={
                    <Box display="flex" alignItems="center" gap="$8">
                      <IconPencil color="content.subtle" size={20} />
                      <Typography fontSize="$16" fontWeight="medium">
                        Table Columns
                      </Typography>
                    </Box>
                  }
                >
                  <StepDataTable
                    selectable={!isReadOnly}
                    selected={cachedSelectedTableColumns[table.name] || []}
                    onSelect={(selected) => {
                      setCachedSelectedTableColumns((prev) => {
                        const currentSelected = prev[table.name] || [];
                        const newSelected = typeof selected === 'function' ? selected(currentSelected) : selected;
                        return {
                          ...prev,
                          [table.name]: newSelected,
                        } as Record<string, string[]>;
                      });
                    }}
                    columns={tableEditableColumns}
                    data={columnsData}
                    row={FieldRowItem}
                    rowProps={rowProps}
                    layout="auto"
                    rowCount="all"
                  />
                  {/* Add Column Button */}
                  {!isReadOnly && (
                    <Box marginTop="$8" display="flex" gap="$8">
                      <Button
                        type="button"
                        icon={IconPlus}
                        variant="ghost"
                        round
                        style={{
                          border: '1px solid #DADEE3',
                          backgroundColor: 'white',
                        }}
                      >
                        Add Column
                      </Button>
                    </Box>
                  )}
                </Collapsible>
              )}

              {/* Table Data */}
              {table.data && table.data.length > 0 ? (
                <StepDataDisplayTable
                  columns={columns}
                  data={table.data}
                  row={TableDataRowItem}
                  layout="auto"
                  rowCount="all"
                />
              ) : (
                <Box padding="$24" textAlign="center" borderWidth="1px" borderRadius="$8">
                  <Typography fontSize="$14">No data available for this table</Typography>
                </Box>
              )}
            </Box>
          );
        })}
        {layoutTables.length === 0 && (
          <Box padding="$24" textAlign="center">
            <Typography fontSize="$14">No tables available. Add a table to get started.</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

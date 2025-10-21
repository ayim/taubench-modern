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
import { ChangeEvent, FC, useCallback, useMemo, useState, useEffect } from 'react';

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
    setSelectedFields,
    setSelectedTableColumns,
    flowExecuted,
    setFlowExecuted,
  } = useDocumentIntelligenceStore();

  const effectiveFlowType = currentFlowType || flowType;
  const isParseDocumentFlow = effectiveFlowType === 'parse_current_document';

  const { executeDocumentLayoutFlow, isLoading: flowLoading } = useDocumentLayoutFlow();
  const [busy, setBusy] = useState(false);

  // Initialize cachedSelectedFields based on selectedFields from store
  const [cachedSelectedFields, setCachedSelectedFields] = useState<string[]>(() => {
    if (layoutFields.length > 0 && selectedFields.length > 0) {
      return layoutFields
        .filter((_, index) => selectedFields.includes(index))
        .map(field => field.id); // Use field.id to match Table component expectations
    }
    // If we're in create_data_model_plus_new_layout flow and have fields but no selectedFields,
    // auto-select all fields
    if (layoutFields.length > 0 && effectiveFlowType === 'create_data_model_plus_new_layout' && selectedFields.length === 0) {
      return layoutFields.map(field => field.id); // Use field.id to match Table component expectations
    }
    return [];
  });

  const [cachedSelectedTableColumns, setCachedSelectedTableColumns] = useState<Record<string, string[]>>(() => {
    const tableSelections: Record<string, string[]> = {};
    Object.entries(selectedTableColumns).forEach(([tableName, indices]) => {
      const table = layoutTables.find(t => t.name === tableName);
      if (table && table.columnsMeta) {
        const columnNames = Object.keys(table.columnsMeta);
        tableSelections[tableName] = indices
          .map(index => columnNames[index])
          .filter(Boolean);
      }
    });

    // If we're in create_data_model_plus_new_layout flow and have tables but no selectedTableColumns,
    // auto-select all table columns
    if (layoutTables.length > 0 && effectiveFlowType === 'create_data_model_plus_new_layout' && Object.keys(selectedTableColumns).length === 0) {
      layoutTables.forEach(table => {
        if (table.columnsMeta) {
          tableSelections[table.name] = Object.keys(table.columnsMeta);
        }
      });
    }

    return tableSelections;
  });

  // Initialize flow when component mounts (only once)
  useEffect(() => {
    // Only run the flow for parse_current_document flow and if it hasn't been executed yet
    if (fileRef && threadId && agentId && !isProcessing && !flowLoading && !flowExecuted && effectiveFlowType === 'parse_current_document') {
      setFlowExecuted(true);
      executeDocumentLayoutFlow({
        fileRef,
        threadId,
        agentId,
        dataModelName: documentData.dataModelName,
        flowType: effectiveFlowType,
      }).catch(() => {
        setFlowExecuted(false);
      });
    }
  }, [fileRef, threadId, agentId, effectiveFlowType, documentData.dataModelName, isProcessing, flowLoading, flowExecuted, setFlowExecuted]);



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

      // Validate the new column name
      const trimmedNewName = newColumnName.trim();
      if (!trimmedNewName || trimmedNewName === oldColumnName) {
        return; // Don't update if empty or same as current name
      }

      // Check if the new name already exists in the table
      if (currentTable.columns.includes(trimmedNewName)) {
        return; // Don't update if column name already exists
      }

      // Update columns array - maintain order
      const updatedColumns = currentTable.columns.map(col =>
        col === oldColumnName ? trimmedNewName : col
      );

      // Update columnsMeta - preserve metadata but with new key
      const updatedColumnsMeta = { ...currentTable.columnsMeta };
      if (updatedColumnsMeta[oldColumnName]) {
        updatedColumnsMeta[trimmedNewName] = updatedColumnsMeta[oldColumnName];
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
        { id: 'field', title: 'Field', sortable: true, width: 350 },
        { id: 'value', title: 'Value', sortable: true, width: 400 },
        isReadOnly || isParseDocumentFlow
          ? undefined
          : { id: 'annotate', title: 'Annotate', sortable: false, className: '!text-left', width: 100 },
        isReadOnly ? undefined : { id: 'delete', title: 'Delete', sortable: false, className: '!text-left', width: 80 },
      ].filter((column) => column !== undefined),
    [isReadOnly, isParseDocumentFlow],
  );

  const tableEditableColumns: Column[] = useMemo(
    () =>
      [
        { id: 'field', title: 'Column', sortable: true, width: 180 },
        { id: 'value', title: 'ExampleValue', sortable: true, width: 400 },
        isReadOnly || isParseDocumentFlow
          ? undefined
          : { id: 'annotate', title: 'Annotate', sortable: false, className: '!text-left', width: 100 },
        isReadOnly ? undefined : { id: 'delete', title: 'Delete', sortable: false, className: '!text-left', width: 80 },
      ].filter((column) => column !== undefined),
    [isReadOnly, isParseDocumentFlow],
  );

  const fieldsRowProps = useMemo<FieldRowProps>(
    () => ({
      onChange: handleChangeFieldName,
      onSaveSpecialHandling: handleSaveFieldInstructions,
      onDelete: handleDeleteField,
      showAnnotateButtons: !isReadOnly && !isParseDocumentFlow,
      showDeleteButton: !isReadOnly,
      readOnlyFields: isReadOnly || isParseDocumentFlow,
      label: 'Field',
    }),
    [handleChangeFieldName, handleSaveFieldInstructions, handleDeleteField, isReadOnly, isParseDocumentFlow],
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
          selectable={!isReadOnly && !isParseDocumentFlow}
          selected={cachedSelectedFields}
          onSelect={(selectedFieldIds) => {
            const fieldIds = typeof selectedFieldIds === 'function' ? selectedFieldIds(cachedSelectedFields) : selectedFieldIds;
            setCachedSelectedFields(fieldIds);
            // Convert field IDs back to indices for the store
            const selectedIndices = layoutFields
              .map((field, index) => fieldIds.includes(field.id) ? index : -1)
              .filter(index => index !== -1);
            setSelectedFields(selectedIndices);
          }}
          columns={fieldsColumns}
          data={layoutFields}
          row={FieldRowItem}
          rowProps={fieldsRowProps}
          layout="auto"
          rowCount="all"
          keyId={(field) => field.id}
        />

        {!isParseDocumentFlow && (
          <Box marginTop="$8" display="flex" gap="$8">
            <Button
              type="button"
              icon={IconPlus}
              onClick={handleAddField}
              round
              variant="primary"
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
                const newName = e.target.value.trim();
                // Only update if the name is not empty and different from the current name
                if (newName && newName !== columnId) {
                  handleUpdateColumnName(table.name, columnId, newName);
                }
              }
            },
            onKeyDown: (columnId: string, key: 'name' | 'value') => (e: React.KeyboardEvent<HTMLInputElement>) => {
              if (key === 'name') {
                if (e.key === 'Enter') {
                  const newName = e.currentTarget.value.trim();
                  // Only update if the name is not empty and different from the current name
                  if (newName && newName !== columnId) {
                    handleUpdateColumnName(table.name, columnId, newName);
                  }
                }
              }
            },

            onSaveSpecialHandling: (column: string, instructions: string) => {
              handleSaveTableColumnInstructions(table.name, column, instructions);
            },
            onDelete: (columnId: string) => {
              handleDeleteTableColumn(table.name, columnId);
            },
            showAnnotateButtons: !isReadOnly && !isParseDocumentFlow,
            showDeleteButton: !isReadOnly,
            readOnlyFields: isReadOnly || isParseDocumentFlow,
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
                  {!isReadOnly && !isParseDocumentFlow && (
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
                    selectable={!isReadOnly && !isParseDocumentFlow}
                    selected={cachedSelectedTableColumns[table.name] || []}
                    onSelect={(selectedColumnNames) => {
                      const columnNames = typeof selectedColumnNames === 'function'
                        ? selectedColumnNames(cachedSelectedTableColumns[table.name] || [])
                        : selectedColumnNames;
                      setCachedSelectedTableColumns((prev) => ({
                        ...prev,
                        [table.name]: columnNames,
                      }));
                      // Convert column names back to indices for the store
                      const selectedIndices = columnsData
                        .map((column, index) => columnNames.includes(column.name) ? index : -1)
                        .filter(index => index !== -1);
                      setSelectedTableColumns({
                        ...selectedTableColumns,
                        [table.name]: selectedIndices,
                      });
                    }}
                    columns={tableEditableColumns}
                    data={columnsData}
                    row={FieldRowItem}
                    rowProps={rowProps}
                    layout="auto"
                    rowCount="all"
                    keyId={(column) => column.id}
                  />
                  {/* Add Column Button */}
                  {!isParseDocumentFlow && (
                    <Box marginTop="$8" display="flex" gap="$8">
                      <Button
                        type="button"
                        icon={IconPlus}
                        variant="primary"
                        round

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

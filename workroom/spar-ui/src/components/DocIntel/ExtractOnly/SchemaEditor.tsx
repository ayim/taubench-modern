import { FC, useCallback, useMemo, useState, useRef } from 'react';
import { Box, Typography, Button, Column } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import type { ExtractionSchemaPayload } from '../shared/types';
import { SchemaDataTable } from '../shared/components/SchemaDataTable';
import { SchemaFieldRow, SchemaFieldData, SchemaFieldRowProps } from '../shared/components/SchemaFieldRow';
import {
  addProperty,
  getChildren,
  SchemaNode,
  updateProperty,
  renameProperty,
  jsonPointerToDotNotation,
  dotNotationToJsonPointer,
  parseFieldId,
  walk,
} from '../shared/utils/schema-lib';

/**
 * SchemaEditor - Visual schema builder/editor
 */
interface SchemaEditorProps {
  schema: ExtractionSchemaPayload | null;
  onChange?: (schema: ExtractionSchemaPayload) => void;
  onDeletedFieldsChange?: (deletedFields: Set<string>) => void;
  disabled?: boolean;
}

export const SchemaEditor: FC<SchemaEditorProps> = ({ schema, onChange, onDeletedFieldsChange, disabled = false }) => {
  const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());
  const [deletedFields, setDeletedFields] = useState<Set<string>>(new Set());
  const [pendingFields, setPendingFields] = useState<Map<string, SchemaFieldData>>(new Map());
  const lastAddedFieldRef = useRef<string | null>(null);

  const inputRefCallback = useCallback((element: HTMLInputElement | null, fieldId: string) => {
    if (element && fieldId === lastAddedFieldRef.current) {
      element.focus();
      lastAddedFieldRef.current = null;
    }
  }, []);

  const hasNestedChildProperties = (schemaPayload: ExtractionSchemaPayload, pointer: string): boolean => {
    return getChildren(schemaPayload, pointer).length > 0;
  };

  const calculateNestingDepth = (pointer: string): number => {
    return (pointer.match(/\/properties\//g) || []).length - 1;
  };

  /**
   * Checks if any parent field is deleted by walking up the parent chain.
   * Uses parentMap which stores dot-notation -> parent's dot-notation.
   */
  const isParentDeleted = (
    parentPointer: string | null,
    deletedFieldsSet: Set<string>,
    parentMap: Map<string, string>,
  ): boolean => {
    if (!parentPointer) return false;

    const parentDotNotation = jsonPointerToDotNotation(parentPointer);
    if (!parentDotNotation) return false;

    if (deletedFieldsSet.has(parentDotNotation)) return true;

    const grandparentDotNotation = parentMap.get(parentDotNotation);
    if (!grandparentDotNotation) return false;

    const grandparentPointer = dotNotationToJsonPointer(grandparentDotNotation);
    return grandparentPointer ? isParentDeleted(grandparentPointer, deletedFieldsSet, parentMap) : false;
  };

  /**
   * Builds SchemaFieldData from a SchemaNode.
   */
  const buildFieldData = (
    node: SchemaNode,
    schemaPayload: ExtractionSchemaPayload,
    deletedFieldsSet: Set<string>,
    parentMap: Map<string, string>,
  ): SchemaFieldData | null => {
    // Only process property nodes
    if (!node.key || !node.pointer.startsWith('/properties/')) {
      return null;
    }

    const dotNotationPath = jsonPointerToDotNotation(node.pointer);
    if (!dotNotationPath) return null;

    const nodeSchema = node.schema as { type?: string; description?: string; properties?: unknown; items?: unknown };
    const parentDotNotation = node.parentPointer ? jsonPointerToDotNotation(node.parentPointer) : '';

    if (parentDotNotation) {
      parentMap.set(dotNotationPath, parentDotNotation);
    }

    const fieldName = dotNotationPath.split('.').pop() || '';
    const nestingDepth = calculateNestingDepth(node.pointer);

    return {
      id: dotNotationPath,
      name: fieldName,
      type: nodeSchema.type || 'string',
      description: nodeSchema.description || '',
      isNested: nestingDepth > 0,
      level: nestingDepth,
      parentPath: parentDotNotation || undefined,
      hasChildren: hasNestedChildProperties(schemaPayload, node.pointer),
      deleted: deletedFieldsSet.has(dotNotationPath),
      parentDeleted: isParentDeleted(node.parentPointer, deletedFieldsSet, parentMap),
    };
  };

  const allSchemaFields = useMemo((): SchemaFieldData[] => {
    const fields: SchemaFieldData[] = [];

    if (schema) {
      const parentMap = new Map<string, string>();
      walk(schema, (node: SchemaNode) => {
        const fieldData = buildFieldData(node, schema, deletedFields, parentMap);
        if (fieldData) {
          fields.push(fieldData);
        }
      });
    }

    pendingFields.forEach((field) => {
      fields.push(field);
    });

    return fields;
  }, [schema, deletedFields, pendingFields]);

  const displayedSchemaFields = useMemo((): SchemaFieldData[] => {
    return allSchemaFields.filter(
      (field) => field.level === 0 || !field.parentPath || expandedFields.has(field.parentPath),
    );
  }, [allSchemaFields, expandedFields]);

  const handleToggleExpand = useCallback((fieldId: string) => {
    setExpandedFields((prev) => {
      const updatedExpandedFields = new Set(prev);
      if (updatedExpandedFields.has(fieldId)) {
        updatedExpandedFields.delete(fieldId);
      } else {
        updatedExpandedFields.add(fieldId);
      }
      return updatedExpandedFields;
    });
  }, []);

  /**
   * Returns schema and onChange if both are available, otherwise null.
   */
  const getSchemaContext = useCallback((): {
    schema: ExtractionSchemaPayload;
    onChange: (schema: ExtractionSchemaPayload) => void;
  } | null => {
    if (!schema || !onChange) return null;
    return { schema, onChange };
  }, [schema, onChange]);

  /**
   * Adds a new pending field (not yet in schema).
   */
  const addPendingField = useCallback(() => {
    const pendingId = `pending_${Date.now()}`;
    const pendingField: SchemaFieldData = {
      id: pendingId,
      name: '',
      type: 'string',
      description: '',
      isNested: false,
      level: 0,
      hasChildren: false,
      deleted: false,
      parentDeleted: false,
    };

    setPendingFields((prev) => {
      const updatedPendingFields = new Map(prev);
      updatedPendingFields.set(pendingId, pendingField);
      return updatedPendingFields;
    });

    lastAddedFieldRef.current = pendingId;
  }, []);

  /**
   * Updates a pending field. If name is provided, adds it to the schema.
   * Otherwise, updates the pending field state.
   */
  const updatePendingField = useCallback(
    (pendingId: string, key: 'name' | 'type' | 'description', value: string) => {
      const pendingField = pendingFields.get(pendingId);
      if (!pendingField) return;

      // Always update pending state first
      const updatedPendingField = {
        ...pendingField,
        [key]: value,
      };

      // If name is provided and non-empty, commit to schema
      if (key === 'name' && value.trim()) {
        const schemaContext = getSchemaContext();
        if (!schemaContext) return;

        const updatedSchema = addProperty(schemaContext.schema, '', value.trim(), {
          type: updatedPendingField.type,
          description: updatedPendingField.description,
        }) as ExtractionSchemaPayload;

        setPendingFields((prev) => {
          const updatedPendingFields = new Map(prev);
          updatedPendingFields.delete(pendingId);
          return updatedPendingFields;
        });

        schemaContext.onChange(updatedSchema);
      } else {
        // Update pending state (handles empty name, type, description changes)
        setPendingFields((prev) => {
          const updatedPendingFields = new Map(prev);
          updatedPendingFields.set(pendingId, updatedPendingField);
          return updatedPendingFields;
        });
      }
    },
    [pendingFields, getSchemaContext],
  );

  /**
   * Renames a field in the schema.
   */
  const renameSchemaField = useCallback(
    (fieldId: string, newName: string) => {
      const schemaContext = getSchemaContext();
      if (!schemaContext) return;

      const parsed = parseFieldId(fieldId);
      if (!parsed) return;

      const updatedSchema = renameProperty(
        schemaContext.schema,
        parsed.parentPointer,
        parsed.propertyName,
        newName,
      ) as ExtractionSchemaPayload;
      schemaContext.onChange(updatedSchema);
    },
    [getSchemaContext],
  );

  /**
   * Updates a field's type or description in the schema.
   */
  const updateSchemaFieldProperty = useCallback(
    (fieldId: string, key: 'type' | 'description', value: string) => {
      const schemaContext = getSchemaContext();
      if (!schemaContext) return;

      const parsed = parseFieldId(fieldId);
      if (!parsed) return;

      const updatedSchema = updateProperty(
        schemaContext.schema,
        parsed.parentPointer,
        parsed.propertyName,
        (current) => {
          const currentSchema = current as Record<string, unknown>;
          return {
            ...currentSchema,
            [key]: value,
          };
        },
      ) as ExtractionSchemaPayload;

      schemaContext.onChange(updatedSchema);
    },
    [getSchemaContext],
  );

  /**
   * Handles field changes - routes to appropriate handler based on field type.
   */
  const handleFieldChange = useCallback(
    (fieldId: string, key: 'name' | 'type' | 'description', value: string) => {
      if (pendingFields.has(fieldId)) {
        updatePendingField(fieldId, key, value);
        return;
      }

      if (key === 'name') {
        renameSchemaField(fieldId, value);
      } else {
        updateSchemaFieldProperty(fieldId, key, value);
      }
    },
    [pendingFields, updatePendingField, renameSchemaField, updateSchemaFieldProperty],
  );

  /**
   * Handles field deletion
   */
  const handleDeleteField = useCallback(
    (fieldId: string) => {
      if (pendingFields.has(fieldId)) {
        // Delete pending field
        setPendingFields((prev) => {
          const updatedPendingFields = new Map(prev);
          updatedPendingFields.delete(fieldId);
          return updatedPendingFields;
        });
      } else {
        // Soft delete schema field (marks as deleted in state)
        if (!schema) return;

        const updatedDeletedFields = new Set(deletedFields);
        updatedDeletedFields.add(fieldId);
        setDeletedFields(updatedDeletedFields);

        // Notify parent immediately when deletion happens
        onDeletedFieldsChange?.(updatedDeletedFields);

        if (onChange) {
          onChange(schema);
        }
      }
    },
    [pendingFields, schema, deletedFields, onChange, onDeletedFieldsChange],
  );

  const handleRestoreField = useCallback(
    (fieldId: string) => {
      if (!schema) return;

      const updatedDeletedFields = new Set(deletedFields);
      const field = allSchemaFields.find((f) => f.id === fieldId);
      if (field?.parentPath && deletedFields.has(field.parentPath)) {
        return;
      }

      updatedDeletedFields.delete(fieldId);

      setDeletedFields(updatedDeletedFields);

      // Notify parent immediately when restoration happens
      onDeletedFieldsChange?.(updatedDeletedFields);

      // Notify parent that there are changes (even though schema hasn't changed, restoration is a change)
      if (onChange) {
        onChange(schema);
      }
    },
    [schema, deletedFields, allSchemaFields, onChange, onDeletedFieldsChange],
  );

  const columns: Column[] = useMemo(
    () => [
      { id: 'name', title: 'Name', sortable: false, width: 250 },
      { id: 'type', title: 'Type', sortable: false, width: 150 },
      { id: 'description', title: 'Description', sortable: false, width: 400 },
      { id: 'delete', title: 'Delete', sortable: false, className: '!text-right', width: 32 },
    ],
    [],
  );

  const rowProps: SchemaFieldRowProps = useMemo(
    () => ({
      onChange: handleFieldChange,
      onDelete: handleDeleteField,
      onRestore: handleRestoreField,
      onToggleExpand: handleToggleExpand,
      expandedFields,
      showDeleteButton: !disabled,
      disabled,
      inputRefCallback,
    }),
    [
      handleFieldChange,
      handleDeleteField,
      handleRestoreField,
      handleToggleExpand,
      expandedFields,
      disabled,
      inputRefCallback,
    ],
  );

  if (!schema) {
    return (
      <Box display="flex" flexDirection="column" height="100%">
        <Box
          padding="$12 $16"
          display="flex"
          alignItems="center"
          justifyContent="space-between"
          style={{ borderBottom: '1px solid var(--sema4ai-colors-border-subtle)' }}
        >
          <Typography fontSize="$14" fontWeight="bold">
            Extraction Schema
          </Typography>
        </Box>
        <Box padding="$16" display="flex" alignItems="center" justifyContent="center">
          <Typography color="content.subtle">No schema loaded</Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" height="100%">
      {/* Content */}
      <Box flex="1" overflow="auto" minHeight="0" padding="$16">
        <Box display="flex" flexDirection="column" gap="$12">
          {/* Schema metadata */}
          {typeof schema.title === 'string' && schema.title && (
            <Typography fontSize="$16" fontWeight="bold">
              {schema.title}
            </Typography>
          )}
          {typeof schema.description === 'string' && schema.description && (
            <Typography fontSize="$14" color="content.subtle">
              {schema.description}
            </Typography>
          )}

          {/* Schema Fields Table */}
          <Box marginTop="$8">
            <SchemaDataTable
              selectable={false}
              columns={columns}
              data={displayedSchemaFields}
              row={SchemaFieldRow}
              rowProps={rowProps}
              layout="auto"
              rowCount="all"
              keyId={(field) => field.id}
            />
          </Box>

          {/* Add Field Button */}
          <Box marginTop="$8" display="flex" gap="$8">
            <Button type="button" icon={IconPlus} onClick={addPendingField} round variant="primary" disabled={disabled}>
              Add Field
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

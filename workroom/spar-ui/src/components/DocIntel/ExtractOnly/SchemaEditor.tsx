import { FC, useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { Box, Typography, Button, Column } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import type { ExtractionSchemaPayload } from '../shared/types';
import { SchemaDataTable } from '../shared/components/SchemaDataTable';
import { SchemaFieldRow, SchemaFieldData, SchemaFieldRowProps } from '../shared/components/SchemaFieldRow';
import type { SchemaFieldDefinition } from './utils/schemaUtils';

/**
 * SchemaEditor - Visual schema builder/editor
 */
interface SchemaEditorProps {
  schema: ExtractionSchemaPayload | null;
  onChange?: (schema: ExtractionSchemaPayload) => void;
  disabled?: boolean;
}

export const SchemaEditor: FC<SchemaEditorProps> = ({ schema, onChange, disabled = false }) => {
  // Track which parent fields are expanded
  const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());

  // Track the last added field for auto-focus
  const lastAddedFieldRef = useRef<string | null>(null);

  // Auto-focus newly added field
  useEffect(() => {
    if (lastAddedFieldRef.current) {
      const fieldInput = document.getElementById(`field-name-${lastAddedFieldRef.current}`);
      if (fieldInput) {
        fieldInput.focus();
        lastAddedFieldRef.current = null;
      }
    }
  }, [schema?.properties]);

  // Convert schema properties to flat array for table display
  const allSchemaFields = useMemo((): SchemaFieldData[] => {
    if (!schema?.properties) return [];

    const fields: SchemaFieldData[] = [];

    const processProperties = (
      properties: Record<string, SchemaFieldDefinition>,
      level: number = 0,
      parentPath: string = '',
    ) => {
      Object.entries(properties).forEach(([fieldName, fieldValue]) => {
        const value = fieldValue as SchemaFieldDefinition;
        const fieldPath = parentPath ? `${parentPath}.${fieldName}` : fieldName;
        const hasChildren = Boolean(
          (value.type === 'object' && value.properties) ||
            (value.type === 'array' && value.items?.type === 'object' && value.items?.properties),
        );

        fields.push({
          id: fieldPath,
          name: fieldName.startsWith('__temp_') ? '' : fieldName,
          type: value.type || 'string',
          description: value.description || '',
          isNested: level > 0,
          level,
          parentPath,
          hasChildren,
        });

        // Process nested properties for objects
        if (value.type === 'object' && value.properties) {
          processProperties(value.properties as Record<string, SchemaFieldDefinition>, level + 1, fieldPath);
        }

        // Process array items if they have properties
        if (value.type === 'array' && value.items?.type === 'object' && value.items?.properties) {
          processProperties(value.items.properties as Record<string, SchemaFieldDefinition>, level + 1, fieldPath);
        }
      });
    };

    processProperties(schema.properties as Record<string, SchemaFieldDefinition>, 0, '');
    return fields;
  }, [schema]);

  // Filter fields based on expanded state
  const schemaFieldsData = useMemo((): SchemaFieldData[] => {
    return allSchemaFields.filter((field) => {
      // Always show top-level fields
      if (field.level === 0) return true;

      // For nested fields, check if parent is expanded
      if (field.parentPath) {
        return expandedFields.has(field.parentPath);
      }

      return true;
    });
  }, [allSchemaFields, expandedFields]);

  // Toggle expand/collapse for a field
  const handleToggleExpand = useCallback((fieldId: string) => {
    setExpandedFields((prev) => {
      const next = new Set(prev);
      if (next.has(fieldId)) {
        next.delete(fieldId);
      } else {
        next.add(fieldId);
      }
      return next;
    });
  }, []);

  // Handle field changes
  const handleFieldChange = useCallback(
    (fieldId: string, key: 'name' | 'type' | 'description', value: string) => {
      if (!schema || !onChange) return;

      const pathParts = fieldId.split(/\.|\[\]/);
      const fieldName = pathParts.at(-1) ?? '';

      // For simple top-level fields
      if (pathParts.length === 1) {
        const updatedProperties = { ...schema.properties };
        const field = updatedProperties[fieldName] as SchemaFieldDefinition | undefined;

        if (key === 'name' && value !== fieldName) {
          // Rename field
          updatedProperties[value] = field;
          delete updatedProperties[fieldName];

          // Update required array if needed
          const updatedRequired = schema.required?.map((req) => (req === fieldName ? value : req)) || [];

          onChange({
            ...schema,
            properties: updatedProperties,
            required: updatedRequired,
          });
        } else if (field) {
          // Update field property
          updatedProperties[fieldName] = {
            ...field,
            [key]: value,
          };
          onChange({
            ...schema,
            properties: updatedProperties,
          });
        }
      }
      // TODO: Handle nested field updates for Phase 2
    },
    [schema, onChange],
  );

  // Handle adding new field
  const handleAddField = useCallback(() => {
    if (!schema || !onChange) return;

    // Create a temporary unique key for the new field
    const tempKey = `__temp_${Date.now()}`;
    const updatedProperties = {
      ...schema.properties,
      [tempKey]: {
        type: 'string',
        description: '',
      },
    };

    // Store the temp key so we can auto-focus it
    lastAddedFieldRef.current = tempKey;

    onChange({
      ...schema,
      properties: updatedProperties,
    });
  }, [schema, onChange]);

  // Table columns definition
  const columns: Column[] = useMemo(
    () => [
      { id: 'name', title: 'Name', sortable: false, width: 250 },
      { id: 'type', title: 'Type', sortable: false, width: 150 },
      { id: 'description', title: 'Description', sortable: false, width: 400 },
    ],
    [],
  );

  // Row props
  const rowProps: SchemaFieldRowProps = useMemo(
    () => ({
      onChange: handleFieldChange,
      onToggleExpand: handleToggleExpand,
      expandedFields,
      disabled,
    }),
    [handleFieldChange, handleToggleExpand, expandedFields, disabled],
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
          <>
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
                data={schemaFieldsData}
                row={SchemaFieldRow}
                rowProps={rowProps}
                layout="auto"
                rowCount="all"
                keyId={(field) => field.id}
              />
            </Box>

            {/* Add Field Button */}
            <Box marginTop="$8" display="flex" gap="$8">
              <Button
                type="button"
                icon={IconPlus}
                onClick={handleAddField}
                round
                variant="primary"
                disabled={disabled}
              >
                Add Field
              </Button>
            </Box>
          </>
        </Box>
      </Box>
    </Box>
  );
};

import { Table, Input, Box, TableRowProps, Select, Button } from '@sema4ai/components';
import { FC, useState, useEffect, useRef } from 'react';

export interface SchemaFieldData {
  id: string;
  name: string;
  type: string;
  description?: string;
  isNested?: boolean;
  level?: number;
  parentPath?: string;
  hasChildren?: boolean;
}

export interface SchemaFieldRowProps {
  onChange: (id: string, key: 'name' | 'type' | 'description', value: string) => void;
  onToggleExpand?: (fieldId: string) => void;
  expandedFields?: Set<string>;
  disabled?: boolean;
  onBlur?: (id: string, key: 'name' | 'type' | 'description') => (e: React.FocusEvent<HTMLInputElement>) => void;
}

const TYPE_OPTIONS = [
  { value: 'string', label: 'text' },
  { value: 'number', label: 'number' },
  { value: 'integer', label: 'integer' },
  { value: 'boolean', label: 'boolean' },
  { value: 'object', label: 'object' },
  { value: 'array', label: 'array' },
];

export const SchemaFieldRow: FC<TableRowProps<SchemaFieldData, SchemaFieldRowProps>> = ({ rowData, props }) => {
  const { onChange, onToggleExpand, expandedFields, disabled, onBlur } = props;

  const [localName, setLocalName] = useState(rowData.name);
  const [localDescription, setLocalDescription] = useState(rowData.description || '');

  const prevFieldIdRef = useRef(rowData.id);
  const descriptionTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Sync props only when field ID changes to prevent overwriting local state during typing
  useEffect(() => {
    if (prevFieldIdRef.current !== rowData.id) {
      if (descriptionTimeoutRef.current) {
        clearTimeout(descriptionTimeoutRef.current);
        descriptionTimeoutRef.current = null;
      }
      setLocalName(rowData.name);
      setLocalDescription(rowData.description || '');
      prevFieldIdRef.current = rowData.id;
    }

    return () => {
      if (descriptionTimeoutRef.current) {
        clearTimeout(descriptionTimeoutRef.current);
      }
    };
  }, [rowData.id, rowData.name, rowData.description]);

  const indent = (rowData.level || 0) * 32;
  const isExpanded = expandedFields?.has(rowData.id) ?? false;
  const hasChildren = rowData.hasChildren ?? false;

  // Get row styling based on nesting level
  const rowStyle: React.CSSProperties = {};
  if ((rowData.level || 0) > 0) {
    rowStyle.backgroundColor = 'rgba(229, 231, 235, 0.25)';
    rowStyle.borderLeft = '4px solid rgba(64, 176, 50, 0.4)';
  }

  return (
    <Table.Row data-field-id={rowData.id} style={rowStyle}>
      <Table.Cell>
        <Box display="flex" alignItems="center" gap="$4" style={{ paddingLeft: `${indent}px` }}>
          {hasChildren ? (
            <Button
              variant="ghost"
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand?.(rowData.id);
              }}
              disabled={disabled}
              style={{
                minWidth: '24px',
                width: '24px',
                height: '24px',
                padding: '0',
                fontSize: '14px',
              }}
            >
              {isExpanded ? '▼' : '▶'}
            </Button>
          ) : (
            <Box style={{ width: '24px' }} />
          )}

          <Input
            key={rowData.id}
            id={`field-name-${rowData.id}`}
            name={`field-name-${rowData.id}`}
            aria-label="Field name"
            placeholder="Field name"
            value={localName}
            onChange={(e) => {
              setLocalName(e.target.value);
            }}
            onBlur={(e) => {
              if (e.target.value !== rowData.name) {
                onChange(rowData.id, 'name', e.target.value);
              }
              onBlur?.(rowData.id, 'name')(e);
            }}
            onClick={(e) => {
              e.stopPropagation();
            }}
            style={{
              minWidth: '120px',
              maxWidth: '220px',
            }}
            disabled={disabled}
          />
        </Box>
      </Table.Cell>

      <Table.Cell>
        <Select
          aria-label="Field type"
          value={rowData.type}
          onChange={(value) => onChange(rowData.id, 'type', value)}
          disabled={disabled}
          items={TYPE_OPTIONS}
        />
      </Table.Cell>

      <Table.Cell>
        <Input
          key={`${rowData.id}-description`}
          id={`field-description-${rowData.id}`}
          name={`field-description-${rowData.id}`}
          aria-label="Field description"
          placeholder="Description"
          value={localDescription}
          onChange={(e) => {
            const newValue = e.target.value;
            setLocalDescription(newValue);
            if (descriptionTimeoutRef.current) {
              clearTimeout(descriptionTimeoutRef.current);
            }
            descriptionTimeoutRef.current = setTimeout(() => {
              onChange(rowData.id, 'description', newValue);
            }, 300);
          }}
          onBlur={(e) => {
            if (descriptionTimeoutRef.current) {
              clearTimeout(descriptionTimeoutRef.current);
              descriptionTimeoutRef.current = null;
            }
            if (e.target.value !== rowData.description) {
              onChange(rowData.id, 'description', e.target.value);
            }
            onBlur?.(rowData.id, 'description')(e);
          }}
          onClick={(e) => {
            e.stopPropagation();
          }}
          style={{
            minWidth: '180px',
            width: '100%',
          }}
          disabled={disabled}
        />
      </Table.Cell>
    </Table.Row>
  );
};

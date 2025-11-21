import { Table, Input, Box, TableRowProps, Select, Button, Tooltip } from '@sema4ai/components';
import { IconTrash } from '@sema4ai/icons';
import { FC, useState, useEffect, useMemo } from 'react';
import { StyledDeleteButton } from '../../DocumentIntelligence/components/common/styles';

export interface SchemaFieldData {
  id: string;
  name: string;
  type: string;
  description?: string;
  isNested?: boolean;
  level?: number;
  parentPath?: string;
  hasChildren?: boolean;
  isNewField?: boolean;
}

export interface SchemaFieldRowProps {
  onChange: (id: string, key: 'name' | 'type' | 'description', value: string) => void;
  onDelete?: (id: string) => void;
  onToggleExpand?: (fieldId: string) => void;
  expandedFields?: Set<string>;
  showDeleteButton?: boolean;
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
  const { onChange, onDelete, onToggleExpand, expandedFields, showDeleteButton, disabled, onBlur } = props;

  const [localName, setLocalName] = useState(rowData.name);
  const [localDescription, setLocalDescription] = useState(rowData.description || '');

  useEffect(() => {
    setLocalName(rowData.name);
    setLocalDescription(rowData.description || '');
  }, [rowData.name, rowData.description]);

  const indent = (rowData.level || 0) * 32;
  const isExpanded = expandedFields?.has(rowData.id) ?? false;
  const hasChildren = rowData.hasChildren ?? false;

  // Get row styling based on nesting level
  const rowStyle = useMemo(() => {
    if ((rowData.level || 0) === 0) return {};

    return {
      backgroundColor: 'rgba(229, 231, 235, 0.25)',
      borderLeft: '4px solid rgba(64, 176, 50, 0.4)',
    };
  }, [rowData.level]);

  return (
    <Table.Row data-field-id={rowData.id} style={rowStyle}>
      <Table.Cell>
        <Box display="flex" alignItems="center" gap="$4" style={{ paddingLeft: `${indent}px` }}>
          {/* NEW indicator for fields not yet extracted */}
          {rowData.isNewField && (
            <Tooltip text="New field - will be extracted on re-run" placement="top">
              <Box
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: '#f97316',
                  flexShrink: 0,
                }}
              />
            </Tooltip>
          )}

          {/* Expand/Collapse button for fields with children */}
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
              onChange(rowData.id, 'name', e.target.value);
            }}
            onBlur={onBlur?.(rowData.id, 'name')}
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
            setLocalDescription(e.target.value);
            onChange(rowData.id, 'description', e.target.value);
          }}
          onBlur={onBlur?.(rowData.id, 'description')}
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

      {showDeleteButton && onDelete && (
        <Table.Cell style={{ textAlign: 'left' }}>
          <StyledDeleteButton
            aria-label="Delete Field"
            size="medium"
            variant="outline"
            icon={IconTrash}
            onClick={(e) => {
              e.stopPropagation();
              onDelete(rowData.id);
            }}
            disabled={disabled}
            round
          />
        </Table.Cell>
      )}
    </Table.Row>
  );
};

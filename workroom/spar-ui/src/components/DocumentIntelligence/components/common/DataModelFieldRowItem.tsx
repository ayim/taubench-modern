import { Table, Typography, Select, Checkbox, Input, Box, TableRowProps } from '@sema4ai/components';
import { FC } from 'react';
import { LayoutFieldRow } from '../../types';

interface DataModelFieldRowProps {
  onFieldContextChange: (id: string, context: string | undefined) => void;
  onFieldTypeChange: (id: string, type: string) => void;
  onFieldRequiredChange: (id: string, required: boolean) => void;
  isReadOnly?: boolean;
}

export const DataModelFieldRowItem: FC<TableRowProps<LayoutFieldRow, DataModelFieldRowProps>> = ({
  rowData,
  props
}) => {
  const { onFieldContextChange, onFieldTypeChange, onFieldRequiredChange, isReadOnly } = props;

  const dataTypeOptions = [
    { value: 'string', label: 'String' },
    { value: 'number', label: 'Number' },
    { value: 'date', label: 'Date' },
    { value: 'boolean', label: 'Boolean' },
    { value: 'array', label: 'Array' },
    { value: 'object', label: 'Object' },
  ];

  return (
    <Table.Row
      aria-disabled={isReadOnly}
      data-disabled={isReadOnly}
      data-field-id={rowData.id}
      style={{
        cursor: 'pointer',
      }}
    >
      <Table.Cell>
        <Typography
          fontSize="$16"
          fontWeight="medium"
          style={{
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
            maxWidth: '200px',
            minWidth: '200px',
          }}
        >
          {rowData.name}
        </Typography>
      </Table.Cell>
      <Table.Cell>
        <Typography
          fontSize="$16"
          style={{
            maxWidth: '190px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {rowData.value || '-'}
        </Typography>
      </Table.Cell>
      <Table.Cell>
        <Select
          items={dataTypeOptions}
          value={rowData.type}
          onChange={(e) => onFieldTypeChange(rowData.id, e)}
          style={{ minWidth: '100px' }}
          aria-label="Select data type"
          disabled={isReadOnly}
        />
      </Table.Cell>
      <Table.Cell>
        <Box display="flex" alignItems="center" justifyContent="center">
          <Checkbox
            checked={rowData.required}
            onChange={(e) => onFieldRequiredChange(rowData.id, e.target.checked)}
            aria-label="Field is required"
            disabled={isReadOnly}
          />
        </Box>
      </Table.Cell>
      <Table.Cell>
        <Input
          label=""
          value={rowData.description || ''}
          onChange={(e) => onFieldContextChange(rowData.id, e.target.value)}
          placeholder="Field description"
          style={{ minWidth: '200px' }}
          disabled={isReadOnly}
        />
      </Table.Cell>
    </Table.Row>
  );
};

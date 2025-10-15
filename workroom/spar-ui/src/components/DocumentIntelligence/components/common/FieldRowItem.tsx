import { Table, Typography, Input, Box, TableRowProps } from '@sema4ai/components';
import { IconCursorText, IconPencil, IconTrash } from '@sema4ai/icons';
import { FC, useState, useEffect } from 'react';
import { useDocumentIntelligenceStore } from '../../store/useDocumentIntelligenceStore';
import { LayoutFieldRow, FieldRowProps } from '../../types';
import { StyledEditButton, StyledDeleteButton } from './styles';
import { SpecialHandlingMenu } from './SpecialHandlingMenu';


export const FieldRowItem: FC<TableRowProps<LayoutFieldRow, FieldRowProps>> = ({ rowData, props }) => {
  const {
    onChange,
    onDelete,
    showAnnotateButtons,
    readOnlyFields,
    onBlur,
    onKeyDown,
    onSaveSpecialHandling,
    label = 'Field',
  } = props;
  const { setSelectedFieldId, selectedFieldId } = useDocumentIntelligenceStore();

  const [localValue, setLocalValue] = useState(rowData.name);

  useEffect(() => {
    setLocalValue(rowData.name);
  }, [rowData.name]);

  const handleRowClick = () => {
    const newSelectedId = selectedFieldId === rowData.id ? null : rowData.id;
    setSelectedFieldId(newSelectedId);
  };

  const isSelected = selectedFieldId === rowData.id;
  const shouldHighlight = isSelected;

  return (
    <Table.Row
      aria-disabled={props.showAnnotateButtons === false}
      data-disabled={props.showAnnotateButtons === false}
      data-field-id={rowData.id}
      onClick={handleRowClick}
      style={{
        cursor: 'pointer',
        backgroundColor: shouldHighlight ? 'rgba(64, 176, 50, 0.1)' : 'transparent',
        border: shouldHighlight ? '2px solid rgba(64, 176, 50, 0.3)' : '2px solid transparent',
        borderRadius: shouldHighlight ? '8px' : '0px',
        transition: 'all 0.2s ease-in-out',
      }}
    >
      <Table.Cell>
        {!showAnnotateButtons || readOnlyFields ? (
          <Typography fontSize="$16" fontWeight="medium">
            {rowData.name}
          </Typography>
        ) : (
          <Input
            key={rowData.id}
            aria-label="Field name"
            placeholder="Field name"
            value={localValue}
            onChange={(e) => {
              setLocalValue(e.target.value);
              onChange(rowData.id, 'name')(e);
            }}
            onBlur={onBlur?.(rowData.id, 'name')}
            onKeyDown={onKeyDown?.(rowData.id, 'name')}
            onClick={(e) => {
              e.stopPropagation();
            }}
            className="min-w-[180px]"
            disabled={!showAnnotateButtons}
          />
        )}
      </Table.Cell>

      <Table.Cell>
        <Typography
          fontSize="$16"
          fontWeight="medium"
          style={{
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
            maxWidth: '250px',
          }}
        >
          {rowData.value}
        </Typography>
      </Table.Cell>

      {showAnnotateButtons && (
        <Table.Cell style={{ textAlign: 'left' }}>
          <Box display="flex" gap="$8" alignItems="center">
            <SpecialHandlingMenu
              fieldId={rowData.id}
              fieldName={rowData.name}
              currentInstructions={rowData.layout_description || ''}
              onSave={onSaveSpecialHandling}
              onCancel={() => {}}
              label={label}
              trigger={
                <StyledEditButton
                  aria-label="Edit Annotation"
                  size="medium"
                  variant="outline"
                  icon={IconCursorText}
                  iconAfter={IconPencil}
                  disabled={!showAnnotateButtons}
                  round
                />
              }
            />
          </Box>
        </Table.Cell>
      )}

      {showAnnotateButtons && onDelete && (
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
            disabled={!showAnnotateButtons}
            round
          />
        </Table.Cell>
      )}
    </Table.Row>
  );
};

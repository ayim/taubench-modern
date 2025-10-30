import { Table, Typography, TableRowProps } from '@sema4ai/components';
import { FC } from 'react';
import { useDocumentIntelligenceStore } from '../../store/useDocumentIntelligenceStore';


export const TableDataRowItem: FC<TableRowProps<Record<string, string>, never>> = ({ rowData }) => {
  const setSelectedFieldId = useDocumentIntelligenceStore((state) => state.setSelectedFieldId);
  const selectedFieldId = useDocumentIntelligenceStore((state) => state.selectedFieldId);

  const rowIdentifier = Object.values(rowData).find((value) => value?.trim()) || Object.keys(rowData).join('-');
  const tableRowId = `table-row-${rowIdentifier}`;

  const handleRowClick = () => {
    const newSelectedId = selectedFieldId === tableRowId ? null : tableRowId;
    setSelectedFieldId(newSelectedId);
  };


  const isSelected = selectedFieldId === tableRowId;
  const shouldHighlight = isSelected;

  return (
    <Table.Row
      data-field-id={tableRowId}
      onClick={handleRowClick}
      style={{
        cursor: 'pointer',
        backgroundColor: shouldHighlight ? 'rgba(64, 176, 50, 0.1)' : 'transparent',
        border: shouldHighlight ? '2px solid rgba(64, 176, 50, 0.3)' : '2px solid transparent',
        borderRadius: shouldHighlight ? '8px' : '0px',
        transition: 'all 0.2s ease-in-out',
      }}
    >
      {Object.entries(rowData).map(([key, value]) => (
        <Table.Cell key={`cell-${tableRowId}-${key}-${value}`}>
          <Typography fontSize="$14" style={{ wordBreak: 'break-word', overflowWrap: 'break-word', minWidth: '150px' }}>
            {value}
          </Typography>
        </Table.Cell>
      ))}
    </Table.Row>
  );
};

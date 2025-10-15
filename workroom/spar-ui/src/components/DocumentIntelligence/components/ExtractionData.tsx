import { FC, memo } from 'react';
import { Box, Divider, Typography } from '@sema4ai/components';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import { getTableColumns } from '../types';
import { StepDataTable } from './common/StepDataTable';
import { TableDataRowItem } from './common/TableDataRowItem';

export const ExtractionData: FC = memo(() => {
  const { layoutFields: localFields, layoutTables: tables } = useDocumentIntelligenceStore();

  return (
    <Box display="flex" flexDirection="column" gap="$32">
      <Box display="flex" flexDirection="column" gap="$16">
        <Typography fontSize="$16" fontWeight="bold">
          Fields
        </Typography>
        {localFields.map((field, index) => (
          <Box key={field.id || index} display="flex" flexDirection="column" gap="$8">
            <Box display="flex" flexDirection="row" alignItems="center" gap="$8">
              <Box width="$8" height="$8" backgroundColor="background.success" borderRadius={360} />
              <Typography fontSize="$14" fontWeight="medium">
                {`${field.name}: `}
              </Typography>
            </Box>
            <Typography fontSize="$14">{field.value}</Typography>
          </Box>
        ))}
        {localFields.length === 0 && (
          <Box padding="$24" textAlign="center">
            <Typography fontSize="$14">No fields available. Add a field to get started.</Typography>
          </Box>
        )}
      </Box>

      <Divider />

      <Box display="flex" flexDirection="column" gap="$16">
        <Typography fontSize="$16" fontWeight="bold">
          Tables
        </Typography>

        {tables.map((table) => (
          <Box key={table.id} marginBottom="$24" flexDirection="column" gap="$16">
            <Typography fontSize="$18" fontWeight="medium" marginBottom="$16">
              {table.name}
            </Typography>

            {table.data && table.data.length > 0 ? (
              <StepDataTable
                columns={getTableColumns(table)}
                data={table.data}
                row={TableDataRowItem}
                layout="auto"
                rowCount="all"
                selectable={false}
              />
            ) : (
              <Box padding="$24" textAlign="center" borderWidth="1px" borderRadius="$8">
                <Typography fontSize="$14">No data available for this table</Typography>
              </Box>
            )}
          </Box>
        ))}
        {tables.length === 0 && (
          <Box padding="$24" textAlign="center">
            <Typography fontSize="$14">No tables available. Add a table to get started.</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
});

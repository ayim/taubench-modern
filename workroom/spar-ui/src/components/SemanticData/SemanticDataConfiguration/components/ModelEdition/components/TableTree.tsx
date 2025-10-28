import { Box, Typography } from '@sema4ai/components';
import { TreeList } from '@sema4ai/layouts';
import { IconDbDatabase } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useFormContext } from 'react-hook-form';

import { DataConnectionFormSchema } from '../../form';
import { InputControlled } from '../../../../../../common/form/InputControlled';
import { TableTreeItem } from './TableTreeItem';

const columns = [
  'Description',
  <Typography>
    Synonyms{' '}
    <Typography fontWeight="normal" color="content.subtle.light" as="span">
      (comma-separated)
    </Typography>
  </Typography>,
];

const Cell = styled.div`
  label {
    display: block;
    height: 100%;

    > div {
      height: 100%;
    }

    textarea {
      min-height: 100%;
    }
  }
`;

export const TableTree = () => {
  const { watch } = useFormContext<DataConnectionFormSchema>();
  const tables = watch('tables');

  if (!tables) {
    return null;
  }

  return (
    <TreeList columns={columns}>
      {tables.map((table, tableIndex) => {
        return (
          <TreeList.Item
            key={table.name}
            label={table.name}
            icon={IconDbDatabase}
            open
            description={table.base_table.table}
            columns={
              <>
                <Cell>
                  <InputControlled
                    fieldName={`tables.${tableIndex}.description`}
                    aria-label="Description"
                    variant="ghost"
                    autoGrow={8}
                  />
                </Cell>
                <Cell>
                  <Box p="$16">-</Box>
                </Cell>
              </>
            }
          >
            {table.dimensions?.map((dimension, dimensionIndex) => {
              return (
                <TableTreeItem
                  type="dimensions"
                  dimension={dimension}
                  dimensionIndex={dimensionIndex}
                  tableIndex={tableIndex}
                />
              );
            })}
            {table.time_dimensions?.map((dimension, dimensionIndex) => {
              return (
                <TableTreeItem
                  type="time_dimensions"
                  dimension={dimension}
                  dimensionIndex={dimensionIndex}
                  tableIndex={tableIndex}
                />
              );
            })}
            {table.facts?.map((dimension, dimensionIndex) => {
              return (
                <TableTreeItem
                  type="facts"
                  dimension={dimension}
                  dimensionIndex={dimensionIndex}
                  tableIndex={tableIndex}
                />
              );
            })}
            {table.metrics?.map((dimension, dimensionIndex) => {
              return (
                <TableTreeItem
                  type="metrics"
                  dimension={dimension}
                  dimensionIndex={dimensionIndex}
                  tableIndex={tableIndex}
                />
              );
            })}
          </TreeList.Item>
        );
      })}
    </TreeList>
  );
};

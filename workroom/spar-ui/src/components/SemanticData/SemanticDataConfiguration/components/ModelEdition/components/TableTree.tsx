import { Box, Typography } from '@sema4ai/components';
import { TreeList } from '@sema4ai/layouts';
import { IconDbColumn, IconDbDatabase } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useFormContext } from 'react-hook-form';

import { DataConnectionFormSchema } from '../../form';
import { InputControlled } from '../../../../../../common/form/InputControlled';
import { SynonymField } from './SynonymField';

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
            {table.dimensions.map((dimension, dimensionIndex) => {
              return (
                <TreeList.Item
                  key={dimension.name}
                  label={dimension.name}
                  icon={IconDbColumn}
                  description={`${dimension.data_type.replace('!', '')}`}
                  columns={
                    <>
                      <Cell>
                        <InputControlled
                          fieldName={`tables.${tableIndex}.dimensions.${dimensionIndex}.description`}
                          aria-label="Description"
                          variant="ghost"
                          autoGrow={8}
                        />
                      </Cell>
                      <Cell>
                        <SynonymField
                          tableIndex={tableIndex}
                          dimensionIndex={dimensionIndex}
                          initialValue={dimension.synonyms}
                        />
                      </Cell>
                    </>
                  }
                />
              );
            })}
          </TreeList.Item>
        );
      })}
    </TreeList>
  );
};

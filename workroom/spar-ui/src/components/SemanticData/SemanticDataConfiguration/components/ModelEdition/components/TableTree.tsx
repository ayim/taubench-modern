import { FC } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import { TreeList } from '@sema4ai/layouts';
import { IconCloseSmall, IconDbDatabase, IconDbSchema } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useFormContext } from 'react-hook-form';

import { DataConnectionFormSchema } from '../../form';
import { InputControlled } from '../../../../../../common/form/InputControlled';
import { useSemanticDataValidationQuery } from '../../../../../../queries';
import { TableTreeItem } from './TableTreeItem';
import { snakeCaseToCamelCase } from '../../../../../../common/helpers';

type Props = {
  modelId: string;
};

const columns = [
  'Description',
  <Typography>
    Synonyms{' '}
    <Typography fontWeight="normal" color="content.subtle.light" as="span">
      (comma-separated)
    </Typography>
  </Typography>,
  <Typography>
    Sample Values{' '}
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

const dimensionTypes = ['dimensions', 'time_dimensions', 'facts', 'metrics'] as const;

export const TableTree: FC<Props> = ({ modelId }) => {
  const { data: validation } = useSemanticDataValidationQuery({ modelId });
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const tables = watch('tables');

  if (!tables) {
    return null;
  }

  const handleRemoveTable = (tableIndex: number) => {
    const newTables = [...tables];
    newTables.splice(tableIndex, 1);
    setValue('tables', newTables);
  };

  return (
    <TreeList columns={columns} withActions>
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
                <Cell>
                  <Box p="$16">-</Box>
                </Cell>
                <Cell>
                  {tables.length !== 1 && (
                    <Button
                      variant="ghost-subtle"
                      aria-label="Remove dimension"
                      icon={IconCloseSmall}
                      onClick={() => handleRemoveTable(tableIndex)}
                    />
                  )}
                </Cell>
              </>
            }
          >
            {dimensionTypes.map((type) => {
              const dimensions = table[type];

              if (!dimensions || dimensions.length === 0) {
                return null;
              }

              return (
                <TreeList.Item
                  icon={IconDbSchema}
                  open
                  label={snakeCaseToCamelCase(type)}
                  columns={
                    <>
                      <Cell />
                      <Cell />
                      <Cell />
                      <Cell />
                    </>
                  }
                >
                  {table[type]?.map((dimension, dimensionIndex) => {
                    const errors = validation?.tables
                      ?.find((curr) => curr.base_table.table === table.base_table.table)
                      ?.[type]?.find((curr) => curr.name === dimension.name)?.errors;
                    return (
                      <TableTreeItem
                        key={dimension.name}
                        type={type}
                        dimensions={dimensions}
                        dimensionIndex={dimensionIndex}
                        tableIndex={tableIndex}
                        errors={errors}
                        baseTableName={table.base_table.table}
                      />
                    );
                  })}
                </TreeList.Item>
              );
            })}
          </TreeList.Item>
        );
      })}
    </TreeList>
  );
};

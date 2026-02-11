import { FC, ReactNode } from 'react';
import { Box, Button, EmptyState, Link, Typography } from '@sema4ai/components';
import { TreeList } from '@sema4ai/layouts';
import {
  IconArrowUpRight,
  IconCloseSmall,
  IconDbDatabase,
  IconDbSchema,
  IconDbSpreadsheet,
  IconInformation,
} from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useFormContext } from 'react-hook-form';

import { InputControlled } from '~/components/form/InputControlled';
import { useSemanticDataValidationQuery } from '~/queries/semanticData';
import { snakeCaseToCamelCase } from '~/components/helpers';
import { TableTreeItem } from './TableTreeItem';
import { DataConnectionFormSchema } from '../../form';
import { getTableDimensions } from '../../../../../../lib/SemanticDataModels';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';

type Props = {
  modelId: string;
  emptyAction?: ReactNode;
};

const ErrorMessage = styled(Typography)`
  white-space: normal;
`;

const columns = [
  'Semantic Name',
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

export const TableTree: FC<Props> = ({ modelId, emptyAction }) => {
  const { data: validation } = useSemanticDataValidationQuery({ modelId });
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const { tables, dataSelection } = watch();

  const hasDisplayableContent = tables && tables.some((table) => getTableDimensions(table).length > 0);

  if (!hasDisplayableContent) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" height="100%">
        <EmptyState
          title="Data Model"
          description="Select tables and columns from your data connection to build your data model. Add descriptions and synonyms to help your agent better understand the data."
          action={emptyAction}
          secondaryAction={
            <Link
              icon={IconInformation}
              iconAfter={IconArrowUpRight}
              href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS}
              target="_blank"
              rel="noopener"
              variant="primary"
              fontWeight="medium"
            >
              Learn More
            </Link>
          }
        />
      </Box>
    );
  }

  const handleRemoveTable = (tableName: string, tableIndex: number) => {
    const newTables = [...tables];
    newTables.splice(tableIndex, 1);
    setValue('tables', newTables);

    const newDataSelection = dataSelection.filter((selection) => selection.name !== tableName);
    setValue('dataSelection', newDataSelection);
  };

  return (
    <TreeList columns={columns} withActions>
      {tables.map((table, tableIndex) => {
        const tableDimensions = getTableDimensions(table);

        if (tableDimensions.length === 0) {
          return null;
        }

        const Icon = table.base_table.file_reference ? IconDbSpreadsheet : IconDbDatabase;

        const tableErrors = validation?.tables?.find(
          (curr) => curr.base_table.table === table.base_table.table,
        )?.errors;

        const description = (
          <>
            {table.base_table.table}{' '}
            {tableErrors && (
              <>
                <br />
                <ErrorMessage as="span" color="content.error">
                  {tableErrors.map((error) => error.message).join(', ')}
                </ErrorMessage>
              </>
            )}
          </>
        );

        return (
          <TreeList.Item
            key={table.name}
            label={table.name}
            icon={Icon}
            open
            description={description}
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
                      onClick={() => handleRemoveTable(table.base_table.table, tableIndex)}
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

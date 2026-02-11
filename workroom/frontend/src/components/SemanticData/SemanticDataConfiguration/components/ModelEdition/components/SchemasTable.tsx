import { FC, useMemo } from 'react';
import { Box, Button, EmptyState, Link, Menu, Table, TableRowProps, Typography } from '@sema4ai/components';
import { IconArrowUpRight, IconDotsHorizontal, IconInformation, IconPencil, IconPlus, IconTrash } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { useFormContext } from 'react-hook-form';

import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { DataConnectionFormSchema, SchemaFormItem } from '../../form';

type SchemaRowData = SchemaFormItem & {
  originalIndex: number;
};

const TruncatedDescription = styled(Typography)`
  max-width: 400px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
`;

type RowProps = {
  onEdit: (index: number) => void;
  onDelete: (index: number) => void;
};

const NameCell: FC<{ rowData: SchemaRowData }> = ({ rowData }) => {
  return (
    <Table.Cell>
      <Typography variant="body-medium" truncate>
        {rowData.name}
      </Typography>
    </Table.Cell>
  );
};

const DescriptionCell: FC<{ rowData: SchemaRowData }> = ({ rowData }) => {
  return (
    <Table.Cell>
      <TruncatedDescription variant="body-small">{rowData.description}</TruncatedDescription>
    </Table.Cell>
  );
};

const ActionsCell: FC<RowProps & { rowData: SchemaRowData }> = ({ rowData, onEdit, onDelete }) => {
  return (
    <Table.Cell controls>
      <Menu
        trigger={<Button aria-label="Actions" size="small" icon={IconDotsHorizontal} variant="ghost-subtle" round />}
      >
        <Menu.Item icon={IconPencil} onClick={() => onEdit(rowData.originalIndex)}>
          Edit
        </Menu.Item>
        <Menu.Item icon={IconTrash} onClick={() => onDelete(rowData.originalIndex)}>
          Delete
        </Menu.Item>
      </Menu>
    </Table.Cell>
  );
};

const SchemasTableRow: FC<TableRowProps<SchemaRowData, RowProps>> = ({ rowData, props }) => {
  if (!props) return null;

  const cellComponents: Partial<Record<string, FC<RowProps & { rowData: SchemaRowData }>>> = {
    name: NameCell,
    description: DescriptionCell,
    actions: ActionsCell,
  };

  return (
    <Table.Row onClick={props.onEdit ? () => props.onEdit(rowData.originalIndex) : undefined}>
      {['name', 'description', 'actions'].map((id) => {
        const CellElement = cellComponents[id];
        if (CellElement) {
          return <CellElement key={id} rowData={rowData} {...props} />;
        }
        return null;
      })}
    </Table.Row>
  );
};

type SchemasTableProps = {
  onCreateSchema: () => void;
  onEditSchema: (index: number) => void;
};

export const SchemasTable: FC<SchemasTableProps> = ({ onCreateSchema, onEditSchema }) => {
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const schemas = watch('schemas') || [];

  const tableData = useMemo<SchemaRowData[]>(
    () =>
      schemas.map((schema, index) => ({
        ...schema,
        originalIndex: index,
      })),
    [schemas],
  );

  const filterConfiguration = useMemo(
    () =>
      ({
        id: 'schemas-table',
        label: { singular: 'Schema', plural: 'Schemas' },
        columns: [
          {
            id: 'name',
            title: 'Name',
            sortable: true,
            required: true,
          },
          {
            id: 'description',
            title: 'Description',
            sortable: true,
          },
          {
            id: 'actions',
            title: '',
            width: 32,
            required: true,
          },
        ],
        sort: ['name', 'asc'],
        searchRules: {
          name: { value: (item) => item.name },
          description: { value: (item) => item.description },
        },
        sortRules: {
          name: { type: 'string', value: (item) => item.name },
          description: { type: 'string', value: (item) => item.description },
        },
        contentBefore: (
          <Box display="flex" gap="$8" alignItems="center">
            <Button variant="secondary" icon={IconPlus} round onClick={onCreateSchema}>
              Schema
            </Button>
          </Box>
        ),
      }) satisfies TableWithFilterConfiguration<SchemaRowData>,
    [onCreateSchema],
  );

  const handleDelete = (index: number) => {
    const updatedSchemas = schemas.filter((_, i) => i !== index);
    setValue('schemas', updatedSchemas);
  };

  return (
    <>
      {tableData.length === 0 && (
        <Box display="flex" flexDirection="column" justifyContent="center" height="100%">
          <EmptyState
            title="Schemas"
            description="Define JSON schemas to validate and structure data for your agent. Schemas help ensure data consistency and enable your agent to work with structured data formats."
            action={
              <Button variant="primary" icon={IconPlus} round onClick={onCreateSchema}>
                Add Schema
              </Button>
            }
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
      )}
      {tableData.length > 0 && (
        <TableWithFilter
          {...filterConfiguration}
          data={tableData}
          row={SchemasTableRow}
          rowProps={{
            onEdit: onEditSchema,
            onDelete: handleDelete,
          }}
        />
      )}
    </>
  );
};

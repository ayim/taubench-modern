import { FC, useState, useMemo } from 'react';
import { Box, Button, EmptyState, Link, Menu, Table, TableRowProps, Typography } from '@sema4ai/components';
import { IconArrowUpRight, IconDotsHorizontal, IconInformation, IconPencil, IconPlus, IconTrash } from '@sema4ai/icons';
import { TableWithFilter, TableWithFilterConfiguration } from '@sema4ai/layouts';
import { useFormContext } from 'react-hook-form';

import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { DataConnectionFormSchema } from '../../form';
import { VerifiedQuery } from '~/queries/semanticData';
import { EditVerifiedQueryDialog } from './EditVerifiedQueryDialog';

type VerifiedQueryRowData = VerifiedQuery & {
  created: string;
  originalIndex: number;
};

type RowProps = {
  onEdit: (index: number) => void;
  onDelete: (index: number) => void;
};

const NameCell: FC<{ rowData: VerifiedQueryRowData }> = ({ rowData }) => {
  return (
    <Table.Cell>
      <Typography variant="body-medium" truncate>
        {rowData.name}
      </Typography>
    </Table.Cell>
  );
};

const DescriptionCell: FC<{ rowData: VerifiedQueryRowData }> = ({ rowData }) => {
  return (
    <Table.Cell>
      <Typography
        variant="body-small"
        style={{
          maxWidth: '400px',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {rowData.nlq}
      </Typography>
    </Table.Cell>
  );
};

const CreatedCell: FC<{ rowData: VerifiedQueryRowData }> = ({ rowData }) => {
  return (
    <Table.Cell>
      <Typography variant="body-small" color="content.subtle">
        {rowData.created}
      </Typography>
    </Table.Cell>
  );
};

const ActionsCell: FC<RowProps & { rowData: VerifiedQueryRowData }> = ({ rowData, onEdit, onDelete }) => {
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

const VerifiedQueriesTableRow: FC<TableRowProps<VerifiedQueryRowData, RowProps>> = ({ rowData, props }) => {
  if (!props) return null;

  const cellComponents: Partial<Record<string, FC<RowProps & { rowData: VerifiedQueryRowData }>>> = {
    name: NameCell,
    description: DescriptionCell,
    created: CreatedCell,
    actions: ActionsCell,
  };

  return (
    <Table.Row onClick={props.onEdit ? () => props.onEdit(rowData.originalIndex) : undefined}>
      {['name', 'description', 'created', 'actions'].map((id) => {
        const CellElement = cellComponents[id];
        if (CellElement) {
          return <CellElement key={id} rowData={rowData} {...props} />;
        }
        return null;
      })}
    </Table.Row>
  );
};

type Props = {
  modelId: string;
};

export const VerifiedQueriesTable: FC<Props> = ({ modelId }) => {
  const [isCreateQueryDialogOpen, setIsCreateQueryDialogOpen] = useState(false);
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const verifiedQueries = watch('verifiedQueries') || [];
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} ${diffMins === 1 ? 'min' : 'mins'} ago`;
    if (diffHours < 24) return `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`;
    if (diffDays < 7) return `${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const tableData = useMemo<VerifiedQueryRowData[]>(
    () =>
      verifiedQueries.map((query, index) => ({
        ...query,
        created: formatDate(query.verified_at),
        originalIndex: index,
      })),
    [verifiedQueries],
  );

  const filterConfiguration = useMemo(
    () =>
      ({
        id: 'verified-queries-table',
        label: { singular: 'Verified Query', plural: 'Verified Queries' },
        columns: [
          {
            id: 'name',
            title: 'Name',
            sortable: true,
          },
          {
            id: 'description',
            title: 'Description',
            sortable: true,
          },
          {
            id: 'created',
            title: 'Created',
            sortable: true,
          },
          {
            id: 'actions',
            title: '',
            width: 32,
            required: true,
          },
        ],
        sort: ['createdAt', 'desc'],
        searchRules: {
          name: { value: (item) => item.name },
        },
        sortRules: {
          name: { type: 'string', value: (item) => item.name },
          created: { type: 'date', value: (item) => item.verified_at ?? '' },
        },
        contentBefore: (
          <Box display="flex" gap="$8" alignItems="center">
            <Button variant="secondary" icon={IconPlus} round onClick={() => setIsCreateQueryDialogOpen(true)}>
              Verified Query
            </Button>
          </Box>
        ),
      }) satisfies TableWithFilterConfiguration<VerifiedQueryRowData>,
    [],
  );

  const handleEdit = (index: number) => {
    setEditingIndex(index);
  };

  const handleDelete = (index: number) => {
    const updatedQueries = verifiedQueries.filter((_, i) => i !== index);
    setValue('verifiedQueries', updatedQueries);
  };

  const handleCloseDialog = () => {
    setEditingIndex(null);
  };

  const editingQuery = editingIndex !== null ? verifiedQueries[editingIndex] : null;
  const editingQueryIndex = editingIndex !== null ? editingIndex : -1;

  return (
    <>
      {tableData.length === 0 && (
        <Box display="flex" flexDirection="column" justifyContent="center" height="100%">
          <EmptyState
            title="Verified Queries"
            description="Create verified queries that allow your agents to quickly answer the
            frequently asked questions. Verified queries increase the accuracy, improve
            speed and save tokens."
            action={
              <Button variant="primary" icon={IconPlus} round onClick={() => setIsCreateQueryDialogOpen(true)}>
                Create
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
          row={VerifiedQueriesTableRow}
          rowProps={{
            onEdit: handleEdit,
            onDelete: handleDelete,
          }}
        />
      )}
      {editingQuery && (
        <EditVerifiedQueryDialog
          open
          onClose={handleCloseDialog}
          queryIndex={editingQueryIndex}
          query={editingQuery}
          modelId={modelId}
        />
      )}
      {isCreateQueryDialogOpen && (
        <EditVerifiedQueryDialog
          open={isCreateQueryDialogOpen}
          onClose={() => setIsCreateQueryDialogOpen(false)}
          modelId={modelId}
        />
      )}
    </>
  );
};

import { Badge, Box, EmptyState, Progress, Table, TableRowProps, Typography } from '@sema4ai/components';
import { TableWithFilter } from '@sema4ai/layouts';
import { SortRules } from '@sema4ai/layouts/dist/helpers/search';
import { FC, useCallback, useMemo } from 'react';

import { useWorkItemExecutorsStatusQuery, WorkItemTaskStatusResponseItem } from '../../queries/workItems';
import { useSparUIContext } from '../../api/context';

type ExecutorRowData = WorkItemTaskStatusResponseItem;

const ExecutorRow: FC<TableRowProps<ExecutorRowData>> = ({ rowData }) => {
  const { sparAPIClient } = useSparUIContext();

  const handleWorkItemClick = useCallback(() => {
    if (!rowData.work_item_id) {
      // No work item to navigate to
    }

    // Navigate to the work item - we need to extract agentId from the work_item_id or handle this differently
    // For now, we'll just make it clickable if there's a work_item_id
    // The actual navigation would require knowing the agent_id
    // We'll leave this as a placeholder for now since the API doesn't provide agent_id
  }, [rowData.work_item_id, sparAPIClient]);

  const isExecuting = rowData.status === 'executing';
  const isIdle = rowData.status === 'idle';

  return (
    <Table.Row>
      <Table.Cell align="center">
        <Typography fontWeight="medium">{rowData.task_id}</Typography>
      </Table.Cell>
      <Table.Cell align="center">
        {isExecuting && <Badge variant="info" label="Executing" iconVisible />}
        {isIdle && <Badge variant="secondary" label="Idle" iconVisible />}
        {!isExecuting && !isIdle && <Badge variant="secondary" label={rowData.status} iconVisible />}
      </Table.Cell>
      <Table.Cell>
        {rowData.work_item_id ? (
          <Box
            as="button"
            onClick={handleWorkItemClick}
            style={{
              cursor: 'pointer',
              textAlign: 'left',
              background: 'none',
              border: 'none',
              fontFamily: 'monospace',
            }}
          >
            <Typography fontWeight="medium" style={{ fontFamily: 'monospace' }}>
              {rowData.work_item_id}
            </Typography>
          </Box>
        ) : (
          <Typography color="content.subtle.light">—</Typography>
        )}
      </Table.Cell>
    </Table.Row>
  );
};

export const WorkItemExecutorsView: FC = () => {
  const { data, isLoading } = useWorkItemExecutorsStatusQuery({}, { refetchInterval: 5000 });

  const tableData = useMemo<ExecutorRowData[]>(() => {
    return data?.status || [];
  }, [data]);

  const columns = useMemo(
    () => [
      {
        id: 'task_id',
        title: 'Task ID',
        width: 120,
        align: 'center' as const,
        sortable: true,
      },
      {
        id: 'status',
        title: 'Status',
        width: 150,
        align: 'center' as const,
        sortable: true,
      },
      {
        id: 'work_item_id',
        title: 'Work Item ID',
        minWidth: 300,
        sortable: true,
      },
    ],
    [],
  );

  const searchRules = useMemo(
    () => ({
      work_item_id: {
        value: (item: ExecutorRowData) => item.work_item_id || '',
      },
    }),
    [],
  );

  const sortRules = useMemo<SortRules<ExecutorRowData>>(
    () => ({
      task_id: {
        type: 'number',
        value: (item) => item.task_id,
      },
      status: {
        type: 'string',
        value: (item) => item.status,
      },
      work_item_id: {
        type: 'string',
        value: (item) => item.work_item_id || '',
      },
    }),
    [],
  );

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100%">
        <Progress />
      </Box>
    );
  }

  if (!data?.status || tableData.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100%">
        <EmptyState
          title="No executor status available"
          description="The work items service does not support status reporting or no executors are currently active."
          action={<Box />}
        >
          <Typography>No executor status available</Typography>
        </EmptyState>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" gap={4} pt="$8">
      <Box>
        <TableWithFilter<ExecutorRowData, never>
          id="work-item-executors-table"
          columns={columns}
          data={tableData}
          row={ExecutorRow}
          searchRules={searchRules}
          sortRules={sortRules}
          label={{ singular: 'executor', plural: 'executors' }}
        />
      </Box>
    </Box>
  );
};

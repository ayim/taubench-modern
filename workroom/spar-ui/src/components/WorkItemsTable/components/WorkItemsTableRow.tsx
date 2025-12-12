/* eslint-disable camelcase */
import { Box, Button, Menu, Table, TableRowProps, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import { IconCheck, IconDotsHorizontal, IconRefresh } from '@sema4ai/icons';
import { FC, useCallback } from 'react';

import { formatDateTime, formatShortDateTime } from '../../../common/helpers';
import { useCompleteWorkItemMutation, useRestartWorkItemMutation } from '../../../queries/workItems';
import { useNavigate } from '../../../hooks';
import { WorkItemRowData } from '../types';
import { workItemsTableColumns } from '../columns';
import { WORK_ITEM_STATUS_CONFIG, DEFAULT_WORK_ITEM_STATUS_CONFIG } from '../../../constants/workItemStatus';

type RowProps = {
  rowData: WorkItemRowData;
};

const StatusCell: FC<RowProps> = ({ rowData }) => {
  const { status } = rowData;
  const config = WORK_ITEM_STATUS_CONFIG[status] || DEFAULT_WORK_ITEM_STATUS_CONFIG;

  return (
    <Table.Cell>
      <Box display="flex" alignItems="center" gap="$4">
        <config.icon size="$16" color={config.iconColor} />
        <Typography variant="body-medium">{config.label}</Typography>
      </Box>
    </Table.Cell>
  );
};

const UpdatedAtCell: FC<RowProps> = ({ rowData }) => {
  const timeStampText = rowData.updated_at || '';
  return (
    <Table.Cell>
      <Tooltip text={formatDateTime(timeStampText)} placement="bottom-start">
        <Typography variant="body-small">{formatShortDateTime(timeStampText)}</Typography>
      </Tooltip>
    </Table.Cell>
  );
};

const WorkItemNameCell: FC<RowProps> = ({ rowData }) => {
  const displayName = rowData.work_item_name || '-';
  return (
    <Table.Cell>
      <Typography truncate $nowrap>
        {displayName}
      </Typography>
    </Table.Cell>
  );
};

const ActionsCell: FC<RowProps> = ({ rowData }) => {
  const { addSnackbar } = useSnackbar();
  const { status, work_item_id } = rowData;

  const { mutate: restartWorkItem, isPending: isRestarting } = useRestartWorkItemMutation({
    workItemId: work_item_id ?? '',
  });
  const { mutate: completeWorkItem, isPending: isCompleting } = useCompleteWorkItemMutation({
    workItemId: work_item_id ?? '',
  });

  const handleRestart = useCallback(() => {
    restartWorkItem(
      {},
      {
        onSuccess: () => {
          addSnackbar({ message: 'Work item restarted successfully', variant: 'success' });
        },
        onError: (error) => {
          const errorMessage = error instanceof Error ? error.message : 'Failed to restart work item';
          addSnackbar({ message: errorMessage, variant: 'danger' });
        },
      },
    );
  }, [restartWorkItem, addSnackbar]);

  const handleComplete = useCallback(() => {
    completeWorkItem(
      {},
      {
        onSuccess: () => {
          addSnackbar({ message: 'Work item completed successfully', variant: 'success' });
        },
        onError: (error) => {
          const errorMessage = error instanceof Error ? error.message : 'Failed to complete work item';
          addSnackbar({ message: errorMessage, variant: 'danger' });
        },
      },
    );
  }, [completeWorkItem, addSnackbar]);

  const canRestart = status !== 'PENDING';
  const canComplete = status !== 'COMPLETED' && status !== 'CANCELLED';

  return (
    <Table.Cell controls>
      <Button.Group>
        <Menu trigger={<Button aria-label="Actions" size="small" icon={IconDotsHorizontal} variant="ghost-subtle" />}>
          <Menu.Item icon={IconRefresh} onClick={handleRestart} disabled={!canRestart || isRestarting}>
            Restart
          </Menu.Item>
          <Menu.Item icon={IconCheck} onClick={handleComplete} disabled={!canComplete || isCompleting}>
            Complete
          </Menu.Item>
        </Menu>
      </Button.Group>
    </Table.Cell>
  );
};

const workitemsTableCellComponents: Partial<Record<string, FC<RowProps>>> = {
  work_item_name: WorkItemNameCell,
  status: StatusCell,
  updated_at: UpdatedAtCell,
  actions: ActionsCell,
};

export const WorkItemsTableRow: FC<TableRowProps<WorkItemRowData>> = ({ rowData }) => {
  const navigate = useNavigate();

  const handleRowClick = useCallback(() => {
    const { work_item_id, agent_id, status } = rowData;
    if (status === 'PENDING' || !work_item_id || !agent_id) return;

    navigate({
      to: '/workItem/$agentId/$workItemId',
      params: { workItemId: work_item_id, agentId: agent_id },
      search: { from: 'workItemsListView' },
    });
  }, [rowData, navigate]);

  return (
    <Table.Row onClick={handleRowClick} style={{ cursor: rowData.status === 'PENDING' ? 'default' : 'pointer' }}>
      {workItemsTableColumns.map(({ id }) => {
        const CellElement = workitemsTableCellComponents[id];
        if (CellElement) return <CellElement key={id} rowData={rowData} />;

        return (
          <Table.Cell key={id}>
            <Typography truncate $nowrap>
              {rowData[id as keyof WorkItemRowData] as string}
            </Typography>
          </Table.Cell>
        );
      })}
    </Table.Row>
  );
};

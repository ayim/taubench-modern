/* eslint-disable camelcase */
import { Badge, Button, Menu, Table, TableRowProps, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import {
  IconCheck,
  IconDotsHorizontal,
  IconLoading,
  IconRefresh,
  IconSearchArea,
  IconStatusCompleted,
  IconStatusError,
  IconStatusIdle,
  IconStatusNew,
  IconStatusPending,
} from '@sema4ai/icons';
import { FC, useCallback } from 'react';

import { formatDateTime, snakeCaseToCamelCase } from '../../../common/helpers';
import { useCompleteWorkItemMutation, useRestartWorkItemMutation } from '../../../queries/workItems';
import { useNavigate } from '../../../hooks';
import { WorkItemRowData } from '../types';
import { workItemsTableColumns } from '../columns';

type RowProps = { rowData: WorkItemRowData };

const StatusCell: FC<RowProps> = ({ rowData }) => {
  const { status } = rowData;
  const statusText = snakeCaseToCamelCase(status);

  let badge;
  switch (status) {
    case 'COMPLETED':
      badge = <Badge icon={IconStatusCompleted} iconColor="content.success" label={statusText} variant="green" />;
      break;
    case 'PENDING':
      badge = <Badge icon={IconStatusPending} iconColor="content.subtle" label={statusText} variant="secondary" />;
      break;
    case 'EXECUTING':
      badge = <Badge icon={IconLoading} iconColor="content.subtle" label={statusText} variant="blue" />;
      break;
    case 'NEEDS_REVIEW':
      badge = <Badge icon={IconStatusIdle} iconColor="content.subtle" label={statusText} variant="yellow" />;
      break;
    case 'CANCELLED':
      badge = <Badge icon={IconStatusError} iconColor="content.error" label={statusText} variant="red" />;
      break;
    case 'ERROR':
      badge = <Badge icon={IconStatusError} iconColor="content.error" label={statusText} variant="red" />;
      break;
    case 'INDETERMINATE':
      badge = <Badge icon={IconStatusIdle} iconColor="content.subtle" label={statusText} variant="yellow" />;
      break;
    default:
      badge = <Badge icon={IconStatusNew} iconColor="content.subtle" label={statusText} variant="blue" />;
  }

  return <Table.Cell>{badge}</Table.Cell>;
};

const UpdatedAtCell: FC<RowProps> = ({ rowData }) => {
  const timeStampText = rowData.updated_at || '';
  return (
    <Table.Cell>
      <Tooltip text={timeStampText} placement="bottom-start" maxWidth={400}>
        <Typography>{formatDateTime(timeStampText)}</Typography>
      </Tooltip>
    </Table.Cell>
  );
};

const ActionsCell: FC<RowProps> = ({ rowData }) => {
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();
  const { status, work_item_id, agent_id } = rowData;

  const { mutate: restartWorkItem, isPending: isRestarting } = useRestartWorkItemMutation({
    workItemId: work_item_id ?? '',
  });
  const { mutate: completeWorkItem, isPending: isCompleting } = useCompleteWorkItemMutation({
    workItemId: work_item_id ?? '',
  });

  const handleViewWorkItemClick = useCallback(() => {
    if (status === 'PENDING' || !work_item_id || !agent_id) return;
    
    navigate({ 
      to: '/workItem/$agentId/$workItemId', 
      params: { workItemId: work_item_id, agentId: agent_id } 
    });
  }, [navigate, work_item_id, agent_id, status]);

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

  const canRestart = status !== 'PENDING' && status !== 'EXECUTING';
  const canComplete = status !== 'COMPLETED' && status !== 'CANCELLED';

  return (
    <Table.Cell controls>
      <Button.Group>
        <Button
          aria-label="View Work Item"
          size="small"
          icon={status === 'PENDING' ? IconLoading : IconSearchArea}
          variant="ghost-subtle"
          onClick={status === 'PENDING' ? undefined : handleViewWorkItemClick}
          loading={status === 'PENDING'}
        />
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
  status: StatusCell,
  updated_at: UpdatedAtCell,
  actions: ActionsCell,
};

export const WorkItemsTableRow: FC<TableRowProps<WorkItemRowData, RowProps>> = ({ rowData }) => {
  const navigate = useNavigate();

  const handleRowClick = useCallback(() => {
    const { work_item_id, agent_id, status } = rowData;
    if (status === 'PENDING' || !work_item_id || !agent_id) return;
    
    navigate({ 
      to: '/workItem/$agentId/$workItemId', 
      params: { workItemId: work_item_id, agentId: agent_id } 
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


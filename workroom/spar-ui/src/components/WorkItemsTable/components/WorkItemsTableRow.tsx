/* eslint-disable camelcase */
import { Badge, Button, Menu, Table, TableRowProps, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import {
  IconCheck,
  IconDotsHorizontal,
  IconLoading,
  IconRefresh,
  IconSearchArea,
} from '@sema4ai/icons';
import { FC, useCallback } from 'react';

import { formatDateTime } from '../../../common/helpers';
import { useCompleteWorkItemMutation, useRestartWorkItemMutation } from '../../../queries/workItems';
import { useNavigate } from '../../../hooks';
import { WorkItemRowData } from '../types';
import { workItemsTableColumns } from '../columns';
import { WORK_ITEM_STATUS_CONFIG, DEFAULT_WORK_ITEM_STATUS_CONFIG } from '../../../constants/workItemStatus';
import { createWorkItemsNavigationContext } from '../../../utils/navigation';
import { WorkItemsNavigationContext } from '../../../types/navigation';

type WithNavigationContext = {
  setNavigationContext: (value: WorkItemsNavigationContext | null) => void;
};

type RowProps = { 
  rowData: WorkItemRowData;
};

const StatusCell: FC<RowProps> = ({ rowData }) => {
  const { status } = rowData;
  const config = WORK_ITEM_STATUS_CONFIG[status] || DEFAULT_WORK_ITEM_STATUS_CONFIG;

  return (
    <Table.Cell>
      <Badge
        icon={config.icon}
        iconColor={config.iconColor}
        label={config.label}
        variant={config.variant}
      />
    </Table.Cell>
  );
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

const ActionsCell: FC<RowProps & WithNavigationContext> = ({ rowData, setNavigationContext }) => {
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
    
    const context = createWorkItemsNavigationContext('workItems', 'all');
    if (context) {
      setNavigationContext(context);
    }
    
    navigate({ 
      to: '/workItem/$agentId/$workItemId', 
      params: { workItemId: work_item_id, agentId: agent_id } 
    });
  }, [navigate, work_item_id, agent_id, status, setNavigationContext]);

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

const workitemsTableCellComponents: Partial<Record<string, FC<RowProps & WithNavigationContext>>> = {
  status: StatusCell,
  updated_at: UpdatedAtCell,
  actions: ActionsCell,
};

export const WorkItemsTableRow: FC<TableRowProps<WorkItemRowData, WithNavigationContext>> = ({ rowData, props }) => {
  const navigate = useNavigate();
  const { setNavigationContext } = props;

  const handleRowClick = useCallback(() => {
    const { work_item_id, agent_id, status } = rowData;
    if (status === 'PENDING' || !work_item_id || !agent_id) return;
    
    const context = createWorkItemsNavigationContext('workItems', 'all');
    if (context) {
      setNavigationContext(context);
    }
    
    navigate({ 
      to: '/workItem/$agentId/$workItemId', 
      params: { workItemId: work_item_id, agentId: agent_id } 
    });
  }, [rowData, navigate, setNavigationContext]);

  return (
    <Table.Row onClick={handleRowClick} style={{ cursor: rowData.status === 'PENDING' ? 'default' : 'pointer' }}>
      {workItemsTableColumns.map(({ id }) => {
        const CellElement = workitemsTableCellComponents[id];
        if (CellElement) return <CellElement key={id} rowData={rowData} setNavigationContext={setNavigationContext} />;

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


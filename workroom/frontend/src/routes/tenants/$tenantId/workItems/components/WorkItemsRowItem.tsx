import { Badge, Button, Column, Menu, Table, TableRowProps, Tooltip, Typography } from '@sema4ai/components';
import {
  IconDotsHorizontal,
  IconLoading,
  IconSearchArea,
  IconStatusCompleted,
  IconStatusError,
  IconStatusIdle,
  IconStatusNew,
  IconStatusPending,
  IconStatusProcessing,
} from '@sema4ai/icons';
import { useNavigate } from '@tanstack/react-router';
import { FC, memo, useCallback, useMemo } from 'react';
import { snakeCaseToCamelCase, formatDatetime } from '~/lib/utils';
import { components } from '@sema4ai/agent-server-interface';

type RowData = components['schemas']['WorkItem'] & {
  agent_name: string | null | undefined;
};

type RowProps = {};

export const workitemsTableColumns: Column[] = [
  { id: 'work_item_id', title: 'Work Item ID', resizable: true },
  { id: 'agent_name', title: 'Agent Name', resizable: true },
  { id: 'status', title: 'Status', resizable: false, width: 170 },
  { id: 'updated_at', title: 'Last Updated', resizable: false, width: 130, minWidth: 130 },
  { id: 'actions', title: '', resizable: false, width: 80 },
] as const;

const workitemsTableCellComponents: Partial<Record<string, FC<RowProps & { rowData: RowData }>>> = {
  status: memo(({ rowData }) => {
    const { status } = rowData;

    const statusText = snakeCaseToCamelCase(status);

    const badge = useMemo(() => {
      switch (status) {
        case 'COMPLETED':
          return <Badge icon={IconStatusCompleted} iconColor="content.success" label={statusText} variant="green" />;
        case 'PENDING':
          return <Badge icon={IconStatusPending} iconColor="content.subtle" label={statusText} variant="blue" />;

        case 'EXECUTING':
          return <Badge icon={IconStatusProcessing} iconColor="content.subtle" label={statusText} variant="blue" />;
        case 'NEEDS_REVIEW':
          return <Badge icon={IconStatusIdle} iconColor="content.subtle" label={statusText} variant="yellow" />;
        case 'CANCELLED':
          return <Badge icon={IconStatusError} iconColor="content.error" label={statusText} variant="red" />;
        case 'ERROR':
          return <Badge icon={IconStatusError} iconColor="content.error" label={statusText} variant="red" />;
        case 'INDETERMINATE':
          return <Badge icon={IconStatusIdle} iconColor="content.subtle" label={statusText} variant="yellow" />;
        default:
          return <Badge icon={IconStatusNew} iconColor="content.subtle" label={statusText} variant="blue" />;
      }
    }, [status, statusText]);

    return <Table.Cell>{badge}</Table.Cell>;
  }),
  updated_at: memo(({ rowData }) => {
    const timeStampText = rowData.updated_at || '';
    return (
      <Table.Cell>
        <Tooltip text={timeStampText} placement="bottom-start" maxWidth={400}>
          <Typography>{formatDatetime(timeStampText)}</Typography>
        </Tooltip>
      </Table.Cell>
    );
  }),
  actions: memo(({ rowData }) => {
    const navigate = useNavigate();
    const { status } = rowData;

    const handleViewWorkItemClick = useCallback(() => {
      const { work_item_id, agent_id } = rowData;

      if (work_item_id && agent_id) {
        navigate({
          from: '/tenants/$tenantId/worker/$agentId',
          to: '/tenants/$tenantId/worker/$agentId/$workItemId',
          params: { workItemId: work_item_id, agentId: agent_id },
        });
      }
    }, [navigate, rowData.work_item_id]);

    return (
      <Table.Cell>
        <Button.Group>
          <Button
            aria-label="View Work Item"
            size="small"
            icon={status === 'PENDING' ? IconLoading : IconSearchArea}
            variant="ghost-subtle"
            onClick={status === 'PENDING' ? undefined : handleViewWorkItemClick}
            loading={status === 'PENDING'}
          />
          <Menu
            trigger={
              <Button aria-label="View Work Item" size="small" icon={IconDotsHorizontal} variant="ghost-subtle" />
            }
          >
            <Menu.Item>TODO: Add Required Menu Items</Menu.Item>
          </Menu>
        </Button.Group>
      </Table.Cell>
    );
  }),
};

export const WorkItemsTableRow: FC<TableRowProps<RowData, RowProps>> = ({ rowData }) => {
  return (
    <Table.Row>
      {workitemsTableColumns.map(({ id }) => {
        const CellElement = workitemsTableCellComponents[id];
        if (CellElement) return <CellElement rowData={rowData} />;

        return (
          <Table.Cell key={id}>
            <Typography truncate $nowrap>
              {rowData[id as keyof RowData] as string}
            </Typography>
          </Table.Cell>
        );
      })}
    </Table.Row>
  );
};

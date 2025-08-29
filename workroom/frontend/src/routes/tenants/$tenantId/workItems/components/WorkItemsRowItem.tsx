import {
  Box,
  Checkbox,
  Table,
  TableRowProps,
  Tooltip,
  Menu,
  Button,
  Divider,
  Badge,
  Typography,
} from '@sema4ai/components';
import {
  IconStatusCompleted,
  IconStatusError,
  IconStatusIdle,
  IconStatusNew,
  IconStatusPending,
  IconDotsHorizontal,
  IconCheck,
  IconStatusProcessing,
  IconRefresh2,
  IconShare,
} from '@sema4ai/icons';
import React, { ComponentProps, FC, memo, useCallback, useMemo, forwardRef } from 'react';
import { WorkItem } from '~/types';
import { formatDate } from '~/lib/utils';

interface CellWithIconProps {
  logoIcon: React.ReactNode;
  data: string;
}

interface CellProps {
  data?: string;
}

export interface WorkItemsRowItemProps {
  selectedRows: string[];
  setSelectedRows: React.Dispatch<React.SetStateAction<string[]>>;
  workItems: WorkItem[];
  tenantId: string;
  isRestarting?: boolean;
  handleCompleteWorkItem?: (workItemId: string) => Promise<void>;
  handleRestartWorkItem?: (workItemId: string) => Promise<void>;
}

type CellComponentFC = FC<WorkItemsRowItemProps & { rowData: WorkItem; index: number }>;
type CellComponentMappingType = {
  [key in keyof WorkItem | string]: CellComponentFC;
};

export const CellWithIcon: FC<CellWithIconProps> = memo(({ logoIcon, data }) => {
  return (
    <Box display="flex" alignItems="center" justifyContent="flex-start" gap="5px" className="w-full">
      {logoIcon}
      <Tooltip maxWidth={200} text={data}>
        <Typography variant="body-medium" truncate fontWeight="regular">
          {data}
        </Typography>
      </Tooltip>
    </Box>
  );
});

const CustomCell: FC<CellProps> = memo(({ data }) => {
  return (
    <Table.Cell className="max-w-28">
      <Tooltip maxWidth={300} text={data}>
        <Typography variant="body-medium" truncate fontWeight="regular">
          {data}
        </Typography>
      </Tooltip>
    </Table.Cell>
  );
});

// Function to get stage from status
const getStageFromStatus = (status: string) => {
  switch (status) {
    case 'COMPLETED':
      return 'Completed';
    case 'PENDING':
      return 'Pending';
    case 'EXECUTING':
      return 'Executing';
    case 'NEEDS_REVIEW':
      return 'Needs Review';
    case 'INDETERMINATE':
      return 'Indeterminate';
    default:
      return 'Pending';
  }
};

// Spinning icon component for executing status
const SpinningIcon = forwardRef<HTMLSpanElement, ComponentProps<typeof IconStatusProcessing>>((props, ref) => {
  return <IconStatusProcessing {...props} ref={ref} className="animate-spin" />;
});

// Function to render status badge with appropriate styling
const renderStatusBadge = (status: string) => {
  const statusText = getStageFromStatus(status);

  switch (status) {
    case 'COMPLETED':
      return <Badge icon={IconStatusCompleted} iconColor="content.success" label={statusText} variant="green" />;
    case 'PENDING':
      return <Badge icon={IconStatusPending} iconColor="content.subtle" label={statusText} variant="blue" />;
    case 'EXECUTING':
      return <Badge icon={SpinningIcon} iconColor="content.subtle" label={statusText} variant="blue" />;
    case 'NEEDS_REVIEW':
      return <Badge icon={IconStatusIdle} iconColor="content.subtle" label={statusText} variant="yellow" />;
    case 'CANCELLED':
    case 'FAILED':
      return <Badge icon={IconStatusError} iconColor="content.error" label={statusText} variant="red" />;
    case 'INDETERMINATE':
      return <Badge icon={IconStatusIdle} iconColor="content.subtle" label={statusText} variant="yellow" />;
    default:
      return <Badge icon={IconStatusNew} iconColor="content.subtle" label={statusText} variant="blue" />;
  }
};

const CELL_COMPONENT_MAPPING: CellComponentMappingType = {
  'row-selection': memo(({ selectedRows, rowData, setSelectedRows }) => {
    const isSelected = useMemo(() => selectedRows.includes(rowData.work_item_id), [selectedRows, rowData.work_item_id]);

    const handleRowSelectionUpdate: React.ChangeEventHandler<HTMLInputElement> = useCallback(
      (e) => {
        const isChecked = e.target.checked;

        setSelectedRows((oldSelection) => {
          if (isChecked) {
            return [...oldSelection, rowData.work_item_id];
          }
          return oldSelection.filter((id) => id !== rowData.work_item_id);
        });
      },
      [rowData.work_item_id, setSelectedRows],
    );

    return (
      <Table.Cell className="!pr-0">
        <Box className="flex items-center mr-2 w-fit">
          <Checkbox
            checked={isSelected}
            onChange={handleRowSelectionUpdate}
            aria-label="row-selection-checkbox"
            data-testid="row-selection-checkbox"
            className="row-selection-checkbox"
          />
        </Box>
      </Table.Cell>
    );
  }),

  name: memo(({ rowData }) => {
    // Check if work_item_url exists in the data
    const workItemUrl = rowData.work_item_url;
    const hasValidUrl = workItemUrl && workItemUrl.trim() !== '';

    return (
      <Table.Cell className="max-w-40">
        <Tooltip maxWidth={200} text={`${rowData.work_item_id}`}>
          <div className="w-full">
            <Typography
              variant="body-medium"
              truncate
              color={!hasValidUrl ? 'content.subtle' : 'content.primary'}
              fontWeight="regular"
            >
              {rowData.work_item_id}
            </Typography>
          </div>
        </Tooltip>
      </Table.Cell>
    );
  }),

  agent_name: memo(({ rowData }) => {
    return <CustomCell data={rowData.agent_name || 'N/A'} />;
  }),

  'view-work-item': memo(({ rowData }) => {
    // Check if work_item_url exists and if there's a thread
    let workItemUrl = rowData.work_item_url;
    const hasValidUrl = workItemUrl && workItemUrl.trim() !== '';

    if (hasValidUrl && workItemUrl && rowData.thread_id && rowData.work_item_id && rowData.agent_mode === 'worker') {
      const lastSlashIndex = workItemUrl.lastIndexOf('/');
      if (lastSlashIndex !== -1) {
        const baseUrl = workItemUrl.substring(0, lastSlashIndex);
        workItemUrl = `${baseUrl}/${rowData.work_item_id}_${rowData.thread_id}`;
      }
    }
    // Show the button if there's a URL (temporarily)
    const shouldShowButton = hasValidUrl;

    return (
      <Table.Cell className="max-w-40">
        {shouldShowButton ? (
          <div className="flex items-center">
            <Button
              variant="secondary"
              size="small"
              forwardedAs="a"
              href={workItemUrl}
              target="_blank"
              iconAfter={IconShare}
              round
              rel="noopener noreferrer"
              aria-label="View Work Item content"
              data-testid="work-item-view-button"
              className="whitespace-nowrap w-full"
            >
              <span className="md:hidden">View</span>
              <span className="hidden md:inline">View Work Item</span>
            </Button>
          </div>
        ) : (
          <span className="text-gray-400 text-sm">-</span>
        )}
      </Table.Cell>
    );
  }),

  status: memo(({ rowData }) => {
    return (
      <Table.Cell className="max-w-40 whitespace-nowrap" data-testid="status-cell">
        {renderStatusBadge(rowData.status || 'PENDING')}
      </Table.Cell>
    );
  }),

  created_at: memo(({ rowData }) => {
    const data = useMemo(() => formatDate(rowData.created_at || ''), [rowData.created_at]);
    return <CustomCell data={data} />;
  }),

  updated_at: memo(({ rowData }) => {
    const data = useMemo(() => formatDate(rowData.updated_at || ''), [rowData.updated_at]);
    return <CustomCell data={data} />;
  }),

  actions: memo(({ rowData, handleCompleteWorkItem, handleRestartWorkItem, isRestarting = false }) => {
    return (
      <Table.Cell className="max-w-20">
        <Box className="flex justify-center">
          <Menu
            trigger={
              <Button variant="link">
                <IconDotsHorizontal size={35} />
              </Button>
            }
            placement="bottom-end"
          >
            <Menu.Title>Actions</Menu.Title>
            <Divider />
            {handleRestartWorkItem && (
              <Menu.Item onClick={() => handleRestartWorkItem(rowData.work_item_id)} disabled={isRestarting}>
                <Box display="flex" alignItems="center" gap="5px">
                  <IconRefresh2 size={16} color="blue80" />
                  Restart
                </Box>
              </Menu.Item>
            )}
            {handleCompleteWorkItem && (
              <Menu.Item onClick={() => handleCompleteWorkItem(rowData.work_item_id)} disabled={isRestarting}>
                <Box display="flex" alignItems="center" gap="5px">
                  <IconCheck size={16} color="green80" />
                  Complete
                </Box>
              </Menu.Item>
            )}
          </Menu>
        </Box>
      </Table.Cell>
    );
  }),
};

const getCellComponent = (id: string): CellComponentFC | undefined => {
  return CELL_COMPONENT_MAPPING[id as keyof WorkItem];
};

const RenderCell: FC<{ columnID: string; index: number } & ComponentProps<CellComponentFC>> = memo(
  ({ columnID, ...otherProps }) => {
    const Component = getCellComponent(columnID);

    if (Component) return <Component {...otherProps} />;

    // Fallback for unknown columns
    return <CustomCell data={otherProps.rowData[columnID as keyof WorkItem] as string} />;
  },
);

export const WorkItemsRowItem: FC<TableRowProps<WorkItem, WorkItemsRowItemProps>> = ({ rowData, props, index }) => {
  // Define the exact column order to match the table headers
  const columnOrder = [
    'row-selection',
    'status',
    'name',
    'agent_name',
    'view-work-item',
    'created_at',
    'updated_at',
    'actions',
  ];

  return (
    <Table.Row>
      {columnOrder.map((columnID) => (
        <RenderCell key={columnID} {...{ index, columnID, rowData }} {...props} />
      ))}
    </Table.Row>
  );
};

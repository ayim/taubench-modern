import { Box, Checkbox, Table, TableRowProps, Tooltip, Menu, Button, Divider } from '@sema4ai/components';
import {
  IconShare,
  IconStatusCompleted,
  IconStatusError,
  IconStatusIdle,
  IconStatusNew,
  IconStatusPending,
  IconDotsHorizontal,
  IconCheck,
} from '@sema4ai/icons';
import React, { ComponentProps, FC, memo, useCallback, useMemo } from 'react';
import { Link } from '@tanstack/react-router';
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
        <p className="whitespace-nowrap overflow-hidden text-ellipsis">{data}</p>
      </Tooltip>
    </Box>
  );
});

const CustomCell: FC<CellProps> = memo(({ data }) => {
  return (
    <Table.Cell className="max-w-28">
      <Tooltip maxWidth={200} text={data}>
        <p className="whitespace-nowrap overflow-hidden text-ellipsis">{data}</p>
      </Tooltip>
    </Table.Cell>
  );
});

// Function to render status icon based on status
const renderStatusIcon = (status: string) => {
  switch (status) {
    case 'COMPLETED':
      return <IconStatusCompleted color="green80" />;
    case 'PENDING':
      return <IconStatusPending />;
    case 'CANCELLED':
      return <IconStatusError color="red80" />;
    case 'FAILED':
      return <IconStatusError color="red80" />;
    case 'NEEDS_REVIEW':
      return <IconStatusIdle />;
    case 'INDETERMINATE':
      return <IconStatusIdle />;
    default:
      return <IconStatusNew />;
  }
};

// Function to get stage from status
const getStageFromStatus = (status: string) => {
  switch (status) {
    case 'COMPLETED':
      return 'Completed';
    case 'PENDING':
      return 'Pending';
    case 'NEEDS_REVIEW':
      return 'Needs Review';
    case 'INDETERMINATE':
      return 'Indeterminate';
    default:
      return 'Pending';
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
    // Check if work_item_url exists in the data (it might be a dynamic field)
    const workItemUrl = (rowData as any).work_item_url;

    return (
      <Table.Cell className="max-w-52">
        <Box className="flex flex-row gap-1 items-center overflow-hidden">
          <Tooltip maxWidth={200} text={`Work Item ${rowData.work_item_id}`}>
            {workItemUrl ? (
              <Link
                to={workItemUrl}
                className="whitespace-nowrap overflow-hidden text-ellipsis cursor-pointer hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Work Item {rowData.work_item_id.slice(0, 25)}...
              </Link>
            ) : (
              <p className="whitespace-nowrap overflow-hidden text-ellipsis">
                Work Item {rowData.work_item_id.slice(0, 25)}...
              </p>
            )}
          </Tooltip>
          <button
            type="button"
            className="flex items-center justify-center"
            aria-label="Work Item Details"
            data-testid="work-item-details-button"
            onClick={() => {
              if (workItemUrl) {
                window.open(workItemUrl, '_blank', 'noopener,noreferrer');
              }
            }}
          >
            <IconShare />
          </button>
        </Box>
      </Table.Cell>
    );
  }),

  agent_id: memo(({ rowData }) => {
    return <CustomCell data={rowData.agent_id || 'N/A'} />;
  }),

  status: memo(({ rowData }) => {
    const status = getStageFromStatus(rowData.status || 'PENDING');
    return (
      <Table.Cell className="max-w-44 whitespace-nowrap overflow-hidden text-ellipsis" data-testid="status-cell">
        <CellWithIcon logoIcon={renderStatusIcon(rowData.status || 'PENDING')} data={status} />
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

  actions: memo(({ rowData, handleCompleteWorkItem, isRestarting = false }) => {
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
            {handleCompleteWorkItem && (
              <>
                <Menu.Title>Actions</Menu.Title>
                <Divider />
                <Menu.Item onClick={() => handleCompleteWorkItem(rowData.work_item_id)} disabled={isRestarting}>
                  <Box display="flex" alignItems="center" gap="5px">
                    <IconCheck size={16} color="green80" />
                    Complete Work Item
                  </Box>
                </Menu.Item>
              </>
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
  const columnOrder = ['row-selection', 'name', 'agent_id', 'status', 'created_at', 'updated_at', 'actions'];

  return (
    <Table.Row>
      {columnOrder.map((columnID) => (
        <RenderCell key={columnID} {...{ index, columnID, rowData }} {...props} />
      ))}
    </Table.Row>
  );
};

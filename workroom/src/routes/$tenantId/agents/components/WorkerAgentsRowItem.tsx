import { Badge, Box, Button, Column, Table, TableRowProps } from '@sema4ai/components';
import { FC } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import {
  IconCheckCircle,
  IconWarningTriangle,
  IconPause,
  IconShare,
  IconStatusPending,
  IconStatusProcessing,
  IconStatusNew,
  IconStatusError,
  IconChevronRight,
  IconStatusCompleted,
  IconStatusUnresolved,
} from '@sema4ai/icons';

interface IAgentData {
  id: string;
  name: string;
  state: string;
  documentType: string;
  needsAttention: (string | null | undefined)[];
  failed: (string | null | undefined)[];
  inQueue: (string | null | undefined)[];
  processing: (string | null | undefined)[];
  totalProcessed: (string | null | undefined)[];
}

interface RowItemProps {
  tenantId: string;
  columns: Column[];
}

//function to display the icon for the state column based on the status
const renderStateIcon = (state: string) => {
  switch (state) {
    case 'Ready':
      return <IconCheckCircle color="#141414" />;
    case 'Paused':
      return <IconPause color="#141414" />;
    case 'Failed':
      return <IconWarningTriangle color="#BE1111" />;
    default:
      return <IconStatusNew />;
  }
};

const RowItem: FC<TableRowProps<IAgentData, RowItemProps>> = ({ rowData, props }) => {
  const { tenantId } = props;

  const navigate = useNavigate();

  const handleAgentNameClick = () => {
    // Removing the workitem preference from sessionStorage
    const sessionStorageKey = `ss-${rowData.id}-workitem-id`;
    sessionStorage.removeItem(sessionStorageKey);

    // Navigating to the agent dashboard page
    navigate({
      to: '/$tenantId/$agentId/$threadId',
      params: { tenantId, agentId: rowData.id, threadId: 'dashboard' },
    });
  };

  return (
    <Table.Row>
      {/* Agent Name column with a clickable action */}
      <Table.Cell>
        <div onClick={handleAgentNameClick} className="cursor-pointer flex flex-row items-center gap-1 truncate">
          <p className="whitespace-nowrap overflow-hidden text-ellipsis">{rowData.name}</p>
          <Button aria-label="Agent Dashboard Details" icon={IconShare} size="small" variant="ghost" />
        </div>
      </Table.Cell>

      {/* State with icon */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        <Box display="flex" alignItems="center" justifyContent="flex-start" gap="5px">
          {renderStateIcon(rowData.state)} {rowData.state}
        </Box>
      </Table.Cell>

      {/* Document Type */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        {rowData.documentType}
      </Table.Cell>

      {/* Needs Attention */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        {rowData.needsAttention.length > 0 ? (
          <Link
            to="/$tenantId/$agentId/$threadId"
            params={{
              tenantId,
              agentId: rowData.id,
              threadId: rowData.needsAttention[0] as string,
            }}
            className="cursor-pointer"
          >
            <Badge
              forwardedAs="button"
              icon={IconStatusUnresolved}
              iconAfter={IconChevronRight}
              iconColor="background.notification"
              label={rowData.needsAttention.length}
              variant="orange"
              iconVisible
            />
          </Link>
        ) : (
          <Badge label="0" variant="orange" />
        )}
      </Table.Cell>

      {/* Failed */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        {rowData.failed.length > 0 ? (
          <Link
            to="/$tenantId/$agentId/$threadId"
            params={{ tenantId, agentId: rowData.id, threadId: rowData.failed[0] as string }}
            className="cursor-pointer"
          >
            <Badge
              forwardedAs="button"
              icon={IconStatusError}
              iconAfter={IconChevronRight}
              iconColor="content.error"
              label={rowData.failed.length}
              variant="red"
              iconVisible
            />
          </Link>
        ) : (
          <Badge label="0" variant="red" />
        )}
      </Table.Cell>

      {/* In Queue */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        {rowData.inQueue.length > 0 ? (
          <Link
            to="/$tenantId/$agentId/$threadId"
            params={{ tenantId, agentId: rowData.id, threadId: rowData.inQueue[0] as string }}
            className="cursor-pointer"
          >
            <Badge
              icon={IconStatusPending}
              iconColor="content.primary"
              label={rowData.inQueue.length}
              variant="primary"
            />
          </Link>
        ) : (
          <Badge label="0" variant="primary" />
        )}
      </Table.Cell>

      {/* Processing */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        {rowData.processing.length > 0 ? (
          <Link
            to="/$tenantId/$agentId/$threadId"
            params={{ tenantId, agentId: rowData.id, threadId: rowData.processing[0] as string }}
            className="cursor-pointer"
          >
            <Badge
              icon={IconStatusProcessing}
              iconColor="content.primary"
              label={rowData.processing.length}
              variant="blue"
              className="before:[&>div]:!bg-transparent"
            />
          </Link>
        ) : (
          <Badge label="0" variant="blue" />
        )}
      </Table.Cell>

      {/* Total Processed */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        {rowData.totalProcessed.length > 0 ? (
          <Link
            to="/$tenantId/$agentId/$threadId"
            params={{
              tenantId,
              agentId: rowData.id,
              threadId: rowData.totalProcessed[0] as string,
            }}
            className="cursor-pointer"
          >
            <Badge
              forwardedAs="button"
              icon={IconStatusCompleted}
              iconAfter={IconChevronRight}
              iconColor="content.success"
              label={rowData.totalProcessed.length}
              variant="green"
              iconVisible
            />
          </Link>
        ) : (
          <Badge label="0" variant="green" />
        )}
      </Table.Cell>
    </Table.Row>
  );
};

export default RowItem;

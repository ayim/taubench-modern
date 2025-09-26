import { ThreadTextContent, components } from '@sema4ai/agent-server-interface';
import { Box, Code, Progress, Typography } from '@sema4ai/components';
import {
  IconStatusCompleted,
  IconStatusError,
  IconStatusIdle,
  IconStatusPending,
  IconStatusProcessing,
  IconStatusTerminated,
} from '@sema4ai/icons';
import { FC, memo } from 'react';
import { formatDateTime, formatWorkItemStatus } from '../../common/helpers';
import { useWorkItemQuery } from '../../queries/workItems';

export type WorkItem = components['schemas']['WorkItem'];
export type WorkItemStatus = components['schemas']['WorkItemStatus'];

const TimestampsSection: FC<{ workItem: WorkItem }> = memo(({ workItem }) => {
  return (
    <Box as="section">
      <Typography variant="body-medium" fontWeight="bold" marginBottom="$8">
        Timestamps
      </Typography>
      <Box display="flex" flexDirection="column" gap="$8">
        {workItem.created_at && (
          <Box display="flex" flexDirection="column" gap="$4">
            <Box as="span" fontWeight="medium" minWidth="120px">
              Created At:
            </Box>
            <Box as="span">{formatDateTime(workItem.created_at)}</Box>
          </Box>
        )}
        {workItem.updated_at && (
          <Box display="flex" flexDirection="column" gap="$4">
            <Box as="span" fontWeight="medium" minWidth="120px">
              Updated At:
            </Box>
            <Box as="span">{formatDateTime(workItem.updated_at)}</Box>
          </Box>
        )}
      </Box>
    </Box>
  );
});

const getWorkItemStatusIcon = (status: WorkItemStatus) => {
  switch (status) {
    case 'COMPLETED':
      return <IconStatusCompleted color="content.success" />;
    case 'ERROR':
      return <IconStatusError color="content.error" />;
    case 'EXECUTING':
      return <IconStatusProcessing color="background.notification" />;
    case 'PENDING':
      return <IconStatusPending color="background.notification" />;
    case 'NEEDS_REVIEW':
      return <IconStatusIdle color="background.notification" />;
    case 'CANCELLED':
      return <IconStatusTerminated color="content.error" />;
    case 'INDETERMINATE':
      return <IconStatusIdle color="background.notification" />;
    default:
      return <IconStatusPending color="background.notification" />;
  }
};

const StatusSection: FC<{ workItem: WorkItem }> = memo(({ workItem }) => {
  return (
    <Box as="section">
      <Typography variant="body-medium" fontWeight="bold" marginBottom="$4">
        Status
      </Typography>
      <Box display="flex" gap="$4" alignItems="center">
        {getWorkItemStatusIcon(workItem.status)}
        <Box as="span">{workItem.status ? formatWorkItemStatus(workItem.status) : 'Unknown'}</Box>
      </Box>
    </Box>
  );
});

const MessagesSection: FC<{ workItem: WorkItem }> = memo(({ workItem }) => {
  const textContents = workItem.initial_messages?.flatMap((message) =>
    message.content.filter((content): content is ThreadTextContent => content.kind === 'text'),
  );

  return (
    <Box as="section">
      <Typography variant="body-medium" fontWeight="bold" marginBottom="$4">
        Messages
      </Typography>
      <Box display="flex" flexDirection="column" gap="$3">
        {textContents && textContents.length > 0 ? (
          textContents.map((textContent) => (
            <Box key={textContent.content_id} padding="$3" borderRadius="$2">
              <Box>
                <Box as="span">{textContent.text}</Box>
              </Box>
            </Box>
          ))
        ) : (
          <Box as="span">No messages available</Box>
        )}
      </Box>
    </Box>
  );
});

const PayloadSection: FC<{ workItem: WorkItem }> = memo(({ workItem }) => {
  const { payload } = workItem;

  if (!payload) return null;

  let payloadContent: string;
  try {
    payloadContent = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
  } catch {
    payloadContent = String(payload);
  }

  if (payloadContent === '{}' || payloadContent === '' || payloadContent.trim() === '') {
    payloadContent = 'No payload available';
  }

  return (
    <Box as="section">
      <Typography variant="body-medium" fontWeight="bold" marginBottom={4} id="payload-section">
        Payload
      </Typography>
      <Code theme="light" readOnly lineNumbers={false} value={payloadContent} aria-labelledby="payload-section" />
    </Box>
  );
});

const IdSection: FC<Pick<WorkItem, 'work_item_id'>> = ({ work_item_id: workItemId }) => {
  return (
    <Box as="section">
      <Typography variant="body-medium" fontWeight="bold" marginBottom="$4">
        Work Item ID
      </Typography>
      <Box as="span">{workItemId}</Box>
    </Box>
  );
};

export const WorkItemDetails = ({ workItemId }: { workItemId: string }) => {
  const { data: workItem, isLoading } = useWorkItemQuery({ workItemId });
  if (isLoading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" data-testid="progress">
        <Progress size="large" />
      </Box>
    );
  }

  if (!workItem) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" data-testid="error">
        <Typography color="content.subtle.light">No work item data available</Typography>
      </Box>
    );
  }

  return (
    <Box height="100%" display="flex" flexDirection="column" justifyContent="space-between" px={20} py={16}>
      <Box paddingY="$4" paddingX="$5" display="flex" flexDirection="column" gap="$20">
        <IdSection work_item_id={workItem.work_item_id} />
        <MessagesSection workItem={workItem} />
        <PayloadSection workItem={workItem} />
        <StatusSection workItem={workItem} />
        <TimestampsSection workItem={workItem} />
      </Box>
      <Box height="$16" flexShrink={0} boxShadow="0 -2px 4px 0 rgba(0,0,0,0.05)" />
    </Box>
  );
};

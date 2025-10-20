import { components } from '@sema4ai/agent-server-interface';
import { Box, Tooltip, Typography } from '@sema4ai/components';
import { IconLoading } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useEffect } from 'react';

import { useSparUIContext } from '../../../api/context';
import { formatDateTime } from '../../../common/helpers';
import { SidebarLink } from '../../../common/link';
import { useParams } from '../../../hooks';
import { useWorkItemQuery } from '../../../queries/workItems';

type WorkItem = components['schemas']['WorkItem'];

type WorkItemProps = {
  item: WorkItem;
};

const Container = styled(Box)`
  > a,
  > div {
    overflow: hidden;
    display: block;
    flex: 1;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
`;

const ToolTipContent: FC<Pick<WorkItem, 'created_at' | 'updated_at' | 'status'> & { name: string }> = ({
  name,
  created_at: createdAt,
  updated_at: updatedAt,
  status,
}) => {
  return (
    <>
      <Typography fontWeight="medium" mb="$4">
        {name}
      </Typography>
      <Box display="flex">
        Status:
        <Typography ml="$8" as="span" fontWeight="medium">
          {status}
        </Typography>
      </Box>
      {createdAt && (
        <Box display="flex">
          Created:
          <Typography ml="$8" as="span" fontWeight="medium">
            {formatDateTime(createdAt)}
          </Typography>
        </Box>
      )}
      {updatedAt && (
        <Box display="flex">
          Last updated:
          <Typography ml="$8" as="span" fontWeight="medium">
            {formatDateTime(updatedAt)}
          </Typography>
        </Box>
      )}
    </>
  );
};

export const WorkerItem: FC<WorkItemProps> = ({ item: initialData }) => {
  const {
    agentId,
    threadId: threadIdFromParams,
    workItemId: workItemIdFromParams,
  } = useParams('/workItem/$agentId/$workItemId/$threadId');
  const { data: workItem } = useWorkItemQuery(
    { workItemId: initialData.work_item_id },
    { initialData, enabled: !initialData.thread_id, refetchInterval: 2000 },
  );
  const { sparAPIClient } = useSparUIContext();

  const threadId = workItem?.thread_id;

  /**
   * When new workitem is created, it doesn't have threadId,
   * after some time threadId is attached to the workitem.
   * When this happens and if we are on that workitem,
   * navigate to the threadId route.
   */
  useEffect(() => {
    if (workItemIdFromParams === workItem.work_item_id && !threadIdFromParams && threadId) {
      sparAPIClient.navigate({
        to: '/workItem/$agentId/$workItemId/$threadId',
        params: { agentId, workItemId: workItem.work_item_id, threadId },
      });
    }
  }, [threadIdFromParams, workItemIdFromParams, threadId, agentId, workItem.work_item_id]);

  if (!threadId) {
    return (
      <Container
        display="flex"
        justifyContent="space-between"
        gap="$8"
        pl="$8"
        alignItems="center"
        color="content.subtle.light"
        height={36}
      >
        <Box flex={1}>
          <Typography $nowrap truncate={1}>
            {workItem.work_item_name}
          </Typography>
        </Box>
        <IconLoading />
      </Container>
    );
  }

  return (
    <Tooltip
      text={
        <ToolTipContent
          name={workItem.work_item_name}
          created_at={workItem?.created_at}
          updated_at={workItem?.updated_at}
          status={workItem?.status}
        />
      }
      placement="bottom-end"
      $nowrap
    >
      <Container display="flex" justifyContent="space-between" gap="$8" alignItems="center">
        <SidebarLink
          to="/workItem/$agentId/$workItemId/$threadId"
          params={{ agentId, workItemId: workItem.work_item_id, threadId }}
        >
          {workItem.work_item_name}
        </SidebarLink>
      </Container>
    </Tooltip>
  );
};

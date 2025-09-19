import { Box, Typography } from '@sema4ai/components';
import { IconLoading } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useEffect } from 'react';

import { useSparUIContext } from '../../../api/context';
import { SidebarLink } from '../../../common/link';
import { useParams } from '../../../hooks';
import { useWorkItemQuery } from '../../../queries/workItems';

type WorkItemProps = {
  workItemId: string;
  name: string;
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

export const WorkerItem: FC<WorkItemProps> = ({ workItemId, name }) => {
  const {
    agentId,
    threadId: threadIdFromParams,
    workItemId: workItemIdFromParams,
  } = useParams('/workItem/$agentId/$workItemId/$threadId');
  const { data: workItem } = useWorkItemQuery({ workItemId });
  const { sparAPIClient } = useSparUIContext();

  const threadId = workItem?.thread_id;

  /**
   * When new workitem is created, it doesn't have threadId,
   * after some time threadId is attached to the workitem.
   * When this happens and if we are on that workitem,
   * navigate to the threadId route.
   */
  useEffect(() => {
    if (workItemIdFromParams === workItemId && !threadIdFromParams && threadId) {
      sparAPIClient.navigate({
        to: '/workItem/$agentId/$workItemId/$threadId',
        params: { agentId, workItemId, threadId },
      });
    }
  }, [threadIdFromParams, workItemIdFromParams, threadId, agentId, workItemId]);

  if (!threadId) {
    return (
      <Container
        display="flex"
        justifyContent="space-between"
        gap="$8"
        pl="$8"
        alignItems="center"
        color="content.subtle.light"
      >
        <Box flex={1}>
          <Typography $nowrap truncate={1}>
            {name}
          </Typography>
        </Box>
        <IconLoading />
      </Container>
    );
  }

  return (
    <Container display="flex" justifyContent="space-between" gap="$8" alignItems="center">
      <SidebarLink to="/workItem/$agentId/$workItemId/$threadId" params={{ agentId, workItemId, threadId }}>
        {name}
      </SidebarLink>
    </Container>
  );
};

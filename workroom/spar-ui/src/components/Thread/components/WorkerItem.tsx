import { FC } from 'react';
import { styled } from '@sema4ai/theme';
import { Box, Typography } from '@sema4ai/components';
import { IconLoading } from '@sema4ai/icons';

import { useParams } from '../../../hooks';
import { SidebarLink } from '../../../common/link';
import { useWorkItemQuery } from '../../../queries/workItem';

type ThreadItemProps = {
  workItemId: string;
  name: string;
};

const Container = styled(Box)`
  > a {
    overflow: hidden;
    display: block;
    flex: 1;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
`;

export const WorkerItem: FC<ThreadItemProps> = ({ workItemId, name }) => {
  const { agentId } = useParams('/thread/$agentId/$threadId');
  const { data: workItem } = useWorkItemQuery({ workItemId });

  const threadId = workItem?.thread_id;

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
      <SidebarLink to="/thread/$agentId/$threadId" params={{ threadId, agentId }}>
        {name}
      </SidebarLink>
    </Container>
  );
};

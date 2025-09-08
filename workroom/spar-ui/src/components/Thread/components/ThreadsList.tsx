import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { SidebarMenu } from '@sema4ai/layouts';

import { useParams } from '../../../hooks';
import { useThreadsQuery } from '../../../queries/threads';
import { ThreadItem } from './ThreadItem';

export const ThreadsList: FC = () => {
  const { agentId } = useParams('/conversational/$agentId/$threadId');
  const { data: threads, isLoading } = useThreadsQuery({ agentId });

  // TODO-V2: Loading state for panels?
  if (isLoading) {
    return null;
  }

  return (
    <SidebarMenu name="threads-list" title="Threads list">
      <Box display="flex" alignItems="center" justifyContent="space-between" p="$8" gap="$8">
        <Typography variant="body-medium" fontWeight="medium">
          History
        </Typography>
      </Box>
      <Box display="flex" flexDirection="column">
        {threads?.map((thread) => (
          <ThreadItem key={thread.thread_id} threadId={thread.thread_id || ''} name={thread.name} />
        ))}
      </Box>
    </SidebarMenu>
  );
};

import { FC, useEffect } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { SidebarMenu } from '@sema4ai/layouts';

import { useParams } from '../../../hooks';
import { useThreadsQuery } from '../../../queries/threads';
import { ThreadItem } from './ThreadItem';

export const ThreadsList: FC = () => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { data: threads, isLoading, refetch: refetchThreads } = useThreadsQuery({ agentId });

  /**
   * Sometimes it may happen that we are on some valid $threadId,
   * but react-query client does not have it's information in its cache
   * in that case refreshing the threads query so that new list will
   * containe the thread we are on
   */
  useEffect(() => {
    const hasThread = threads?.some((thread) => thread.thread_id === threadId);
    if (!hasThread) {
      refetchThreads();
    }
  }, [threadId]);

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

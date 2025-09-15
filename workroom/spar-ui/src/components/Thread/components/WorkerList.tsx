import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { SidebarMenu } from '@sema4ai/layouts';

import { useParams } from '../../../hooks';
import { useWorkItemsQuery } from '../../../queries/workItems';
import { WorkerItem } from './WorkerItem';

export const WorkerList: FC = () => {
  const { agentId } = useParams('/thread/$agentId/$threadId');
  const { data: workItems, isLoading } = useWorkItemsQuery({ agentId });

  // TODO-V2: Loading state for panels?
  if (isLoading) {
    return null;
  }

  return (
    <SidebarMenu name="threads-list" title="Threads list">
      <Box display="flex" alignItems="center" justifyContent="space-between" p="$8" gap="$8">
        <Typography variant="body-medium" fontWeight="medium">
          Work Items
        </Typography>
      </Box>
      <Box display="flex" flexDirection="column">
        {workItems?.map((workItem) => (
          <WorkerItem key={workItem.work_item_id} name={workItem.work_item_id} workItemId={workItem.work_item_id} />
        ))}
      </Box>
    </SidebarMenu>
  );
};

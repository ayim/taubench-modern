import { Box, Typography } from '@sema4ai/components';
import { SidebarMenu } from '@sema4ai/layouts';
import { FC } from 'react';

import { useParams } from '../../../hooks';
import { useWorkItemsQuery } from '../../../queries/workItems';
import { WorkerItem } from './WorkerItem';
import { NewWorkItem } from './NewWorkItem';

export const WorkerList: FC = () => {
  const { agentId } = useParams('/workItem/$agentId/$workItemId/$threadId');
  const { data: workItems, isLoading } = useWorkItemsQuery({ agentId });

  // TODO-V2: Loading state for panels?
  if (isLoading) {
    return null;
  }

  return (
    <SidebarMenu name="work-items-list" title="Work Items">
      <Box>
        <Box display="flex" alignItems="center" justifyContent="space-between" p="$8" gap="$8">
          <Typography variant="body-medium" fontWeight="medium">
            Work Items
          </Typography>
        </Box>
        <NewWorkItem />
      </Box>
      <Box display="flex" flexDirection="column">
        {workItems?.map((workItem) => (
          <WorkerItem
            key={workItem.work_item_id}
            name={workItem.work_item_name || workItem.work_item_id}
            workItemId={workItem.work_item_id}
          />
        ))}
      </Box>
    </SidebarMenu>
  );
};

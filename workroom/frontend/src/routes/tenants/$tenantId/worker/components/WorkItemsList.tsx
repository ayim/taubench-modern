import { Box } from '@sema4ai/components';
import { SidebarMenu } from '@sema4ai/layouts';
import { FC } from 'react';
import WorkItemsTable from '../../workItems/components/WorkItemsTable';

export const WorkItemsList: FC = () => {
  return (
    <SidebarMenu name="workitems-list" title="Work Items">
      <Box minWidth={860} height="100%">
        <WorkItemsTable />
      </Box>
    </SidebarMenu>
  );
};

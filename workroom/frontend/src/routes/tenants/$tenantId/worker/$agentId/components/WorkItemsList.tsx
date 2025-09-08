import { Box } from '@sema4ai/components';
import { SidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC } from 'react';
import WorkItemsTable from '../../../workItems/components/WorkItemsTable';

const Container = styled(Box)`
  flex-grow: 1;
  overflow: hidden;
`;

export const WorkItemsList: FC = () => {
  return (
    <SidebarMenu name="work-items-list" title="Work Items List" maxWidth={700}>
      <Container>
        <WorkItemsTable />
      </Container>
    </SidebarMenu>
  );
};

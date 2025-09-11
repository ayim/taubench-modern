import { Box } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { FC } from 'react';
import WorkItemsTable from '../../workItems/components/WorkItemsTable';

const Container = styled(Box)`
  flex-grow: 1;
  overflow: hidden;
`;

export const WorkItemsList: FC = () => {
  return (
    <Container as="section">
      <Box minWidth={860} height="100%">
        <WorkItemsTable />
      </Box>
    </Container>
  );
};

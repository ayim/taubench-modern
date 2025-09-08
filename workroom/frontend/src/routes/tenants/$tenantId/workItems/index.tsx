import { Box } from '@sema4ai/components';
import { createFileRoute } from '@tanstack/react-router';
import WorkItemsTable from './components/WorkItemsTable';

export const Route = createFileRoute('/tenants/$tenantId/workItems/')({
  component: WorkItems,
});

function WorkItems() {
  return (
    <Box overflow="hidden" display="flex" flexDirection="column" gap={4}>
      <WorkItemsTable />
    </Box>
  );
}

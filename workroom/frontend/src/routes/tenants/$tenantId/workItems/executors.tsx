import { createFileRoute } from '@tanstack/react-router';
import { Box } from '@sema4ai/components';
import { WorkItemExecutorsView } from '~/components/WorkItemExecutorsView';

import { Page } from '~/components/layout/Page';

export const Route = createFileRoute('/tenants/$tenantId/workItems/executors')({
  component: Executors,
});

function Executors() {
  return (
    <Page title="Work Items Executors">
      <Box mt="$8">
        <WorkItemExecutorsView />
      </Box>
    </Page>
  );
}

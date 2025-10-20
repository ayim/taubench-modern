import { createFileRoute } from '@tanstack/react-router';
import { WorkItemsTable } from '@sema4ai/spar-ui';

import { Page } from '~/components/layout/Page';

export const Route = createFileRoute('/tenants/$tenantId/workItems/')({
  component: WorkItems,
});

function WorkItems() {
  return (
    <Page title="Work Items">
      <WorkItemsTable />
    </Page>
  );
}

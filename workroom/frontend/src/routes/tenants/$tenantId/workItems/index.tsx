import { createFileRoute } from '@tanstack/react-router';

import { Page } from '~/components/layout/Page';
import WorkItemsTable from './components/WorkItemsTable';

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

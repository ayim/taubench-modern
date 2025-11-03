import { createFileRoute, Outlet } from '@tanstack/react-router';
import { Box } from '@sema4ai/components';
import { WorkItemsTable } from '@sema4ai/spar-ui';

import { Page } from '~/components/layout/Page';
import { NavigationTab, NavigationTabs } from '~/components/NavigationTabs';
import { downloadJSON } from '~/lib/utils';

const tabs = [
  {
    label: 'Overview',
    to: '/tenants/$tenantId/workItems/overview',
  },
  {
    label: 'All Work Items',
    to: '/tenants/$tenantId/workItems/list',
  },
] satisfies NavigationTab[];

export const Route = createFileRoute('/tenants/$tenantId/workItems/list')({
  component: WorkItemsList,
});

function WorkItemsList() {
  return (
    <Page title="Work Items">
      <NavigationTabs tabs={tabs} />
      <Box mt="$8">
        <WorkItemsTable onDownloadJSON={downloadJSON} />
      </Box>
      <Outlet />
    </Page>
  );
}

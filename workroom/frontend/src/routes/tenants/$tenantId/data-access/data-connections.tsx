import { createFileRoute, Outlet } from '@tanstack/react-router';
import { Box } from '@sema4ai/components';
import { DataConnectionTable } from '@sema4ai/spar-ui';

import { Page } from '~/components/layout/Page';
import { NavigationTabs, NavigationTab } from '~/components/NavigationTabs';

const tabs = [
  {
    label: 'Data Connections',
    to: '/tenants/$tenantId/data-access/data-connections',
  },
] satisfies NavigationTab[];

export const Route = createFileRoute('/tenants/$tenantId/data-access/data-connections')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <Page title="Data Access">
      <NavigationTabs tabs={tabs} />
      <Box mt="$8">
        <DataConnectionTable />
      </Box>
      <Outlet />
    </Page>
  );
}

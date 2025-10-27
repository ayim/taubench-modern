import { Box } from '@sema4ai/components';
import { createFileRoute, Outlet } from '@tanstack/react-router';

import { NavigationTab, NavigationTabs } from '~/components/NavigationTabs';
import { useTenantContext } from '~/lib/tenantContext';
import { Page } from '~/components/layout/Page';

export const Route = createFileRoute('/tenants/$tenantId/configuration')({
  component: View,
});

function View() {
  const { features } = useTenantContext();

  const tabs = [
    {
      label: 'LLMs',
      to: '/tenants/$tenantId/configuration/llm',
      hidden: !features.deploymentWizard.enabled,
    },
    {
      label: 'Settings',
      to: '/tenants/$tenantId/configuration/settings',
      hidden: !features.settings.enabled,
    },
    {
      label: 'Document Intelligence',
      to: '/tenants/$tenantId/configuration/documentIntelligence',
      hidden: !features.documentIntelligence.enabled,
    },
  ] satisfies NavigationTab[];

  return (
    <Page title="Configuration">
      <NavigationTabs tabs={tabs} />
      <Box pt="$16">
        <Outlet />
      </Box>
    </Page>
  );
}

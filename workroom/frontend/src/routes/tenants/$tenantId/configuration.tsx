import { Box, Header, Tabs } from '@sema4ai/components';
import { createFileRoute, Outlet, useNavigate } from '@tanstack/react-router';
import { useCallback, useEffect, useState } from 'react';
import { useTenantContext } from '~/lib/tenantContext';

export const Route = createFileRoute('/tenants/$tenantId/configuration')({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  const { features } = useTenantContext();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = useCallback(
    (tabIndex: number) => {
      if (tabIndex === 0) {
        setActiveTab(0);
        navigate({ to: '/tenants/$tenantId/configuration/llm', params: { tenantId } });
      } else if (tabIndex === 1) {
        setActiveTab(1);
        navigate({ to: '/tenants/$tenantId/configuration/settings', params: { tenantId } });
      } else if (tabIndex === 2) {
        setActiveTab(2);
        navigate({ to: '/tenants/$tenantId/configuration/documentIntelligence', params: { tenantId } });
      }
    },
    [navigate, tenantId],
  );

  useEffect(() => {
    handleTabChange(0);
  }, [handleTabChange]);

  return (
    <Box p="$24" pb="$48">
      <Header size="x-large">
        <Header.Title title="Configuration" />
      </Header>
      <Tabs activeTab={activeTab} setActiveTab={handleTabChange}>
        <Tabs.Tab>LLMs</Tabs.Tab>
        <Tabs.Tab>Advanced Configuration</Tabs.Tab>
        {features.documentIntelligence.enabled && <Tabs.Tab>Document Intelligence</Tabs.Tab>}
      </Tabs>
      <Box mt="$8">
        <Outlet />
      </Box>
    </Box>
  );
}

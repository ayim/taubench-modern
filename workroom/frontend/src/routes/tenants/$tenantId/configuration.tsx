import { Box, Header, Tabs } from '@sema4ai/components';
import { createFileRoute, Outlet, useNavigate } from '@tanstack/react-router';
import { useCallback, useEffect, useState } from 'react';

export const Route = createFileRoute('/tenants/$tenantId/configuration')({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = useCallback(
    (tabIndex: number) => {
      if (tabIndex === 0) {
        setActiveTab(0);
        navigate({ to: '/tenants/$tenantId/configuration/llm', params: { tenantId } });
      } else {
        setActiveTab(1);
        navigate({ to: '/tenants/$tenantId/configuration/mcp-servers', params: { tenantId } });
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
        <Tabs.Tab>MCP Servers</Tabs.Tab>
      </Tabs>
      <Box mt="$8">
        <Outlet />
      </Box>
    </Box>
  );
}

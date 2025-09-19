import { createFileRoute } from '@tanstack/react-router';
import { Box, Header, Tabs } from '@sema4ai/components';
import { DataConnectionTable } from '@sema4ai/spar-ui';
import { useState } from 'react';

export const Route = createFileRoute('/tenants/$tenantId/data-access/data-connections/')({
  component: RouteComponent,
});

function RouteComponent() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <Box p="$24" pb="$48">
      <Header size="x-large">
        <Header.Title title="Data Access" />
      </Header>
      <Tabs activeTab={activeTab} setActiveTab={setActiveTab}>
        <Tabs.Tab>Data Connections</Tabs.Tab>
      </Tabs>
      <Box mt="$8">
        <DataConnectionTable />
      </Box>
    </Box>
  );
}

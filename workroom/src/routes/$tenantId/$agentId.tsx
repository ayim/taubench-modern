import { Outlet, createFileRoute } from '@tanstack/react-router';

import { Layout } from './components/Layout';
import { Content } from './components/Content';

export const Route = createFileRoute('/$tenantId/$agentId')({
  component: View,
});

function View() {
  return (
    <Layout>
      <Content>
        <Outlet />
      </Content>
    </Layout>
  );
}

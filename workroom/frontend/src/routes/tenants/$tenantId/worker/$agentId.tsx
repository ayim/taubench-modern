import { createFileRoute, Outlet } from '@tanstack/react-router';
import { Header } from './components/Header';
import { Layout } from './components/Layout';
import { WorkItemsList } from './components/WorkItemsList';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <Layout>
      <Header />
      <WorkItemsList />
      <Outlet />
    </Layout>
  );
}

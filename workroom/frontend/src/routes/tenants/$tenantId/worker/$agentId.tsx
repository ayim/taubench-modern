import { createFileRoute, Outlet, useMatchRoute } from '@tanstack/react-router';
import { Header } from './components/Header';
import { Layout } from './components/Layout';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId')({
  component: RouteComponent,
});

function RouteComponent() {
  const matchRoute = useMatchRoute();

  const isWorkItemListRoute = matchRoute({ to: '/tenants/$tenantId/worker/$agentId' });

  return (
    <Layout workItemListOnly={!!isWorkItemListRoute}>
      <Header />
      <Outlet />
    </Layout>
  );
}

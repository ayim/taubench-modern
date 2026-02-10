import { createFileRoute, Outlet } from '@tanstack/react-router';
import { Worker } from '~/components/Worker';
import { Header } from './components/Header';
import { Layout } from './components/Layout';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <Layout>
      <Header />
      <Worker />
      <Outlet />
    </Layout>
  );
}

import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId')({
  component: RouteComponent,
});

function RouteComponent() {
  return <Outlet />;
}

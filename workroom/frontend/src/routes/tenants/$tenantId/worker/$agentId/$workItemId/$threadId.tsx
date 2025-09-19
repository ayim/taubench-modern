import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId')({
  component: RouteComponent,
});

function RouteComponent() {
  return <Outlet />;
}

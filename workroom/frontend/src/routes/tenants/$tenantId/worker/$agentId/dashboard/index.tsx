import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/dashboard/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <div>Hello "/tenants/$tenantId/worker/$agentId/dashboard/"!</div>;
}

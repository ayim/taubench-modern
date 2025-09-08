import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/files/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <div>Hello "/tenants/$tenantId/worker/$agentId/$workItemId/files/"!</div>;
}

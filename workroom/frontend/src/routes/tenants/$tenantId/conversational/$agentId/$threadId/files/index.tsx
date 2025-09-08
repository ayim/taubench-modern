import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/files/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <div>Hello "/$tenantId/$agentId/$threadId/files"!</div>;
}

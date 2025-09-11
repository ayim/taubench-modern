import { createFileRoute } from '@tanstack/react-router';

import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/files/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <Sidebar name="thread-details">Hello "/$tenantId/$agentId/$threadId/files"!</Sidebar>;
}

import { WorkItemsList } from './components/WorkItemsList';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <WorkItemsList />;
}

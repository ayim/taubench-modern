// import { useWorkItemQuery } from '@sema4ai/spar-ui/queries';
import { WorkItemDetails } from '@sema4ai/spar-ui';
import { createFileRoute } from '@tanstack/react-router';
import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/workitem-details/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { workItemId } = Route.useParams();

  if (!workItemId) {
    return null;
  }

  return (
    <Sidebar name="work-item-details">
      <WorkItemDetails workItemId={workItemId} workItemApiUrl={null} />
    </Sidebar>
  );
}

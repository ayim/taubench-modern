import { FilesView } from '@sema4ai/spar-ui';
import { useWorkItemQuery } from '@sema4ai/spar-ui/queries';
import { createFileRoute } from '@tanstack/react-router';
import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/files/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId, workItemId } = Route.useParams();
  const { data: workItem } = useWorkItemQuery({ workItemId });
  const threadId = workItem?.thread_id;

  if (!threadId) {
    return null;
  }

  return (
    <Sidebar name="thread-details">
      <FilesView threadId={threadId} agentId={agentId} />
    </Sidebar>
  );
}

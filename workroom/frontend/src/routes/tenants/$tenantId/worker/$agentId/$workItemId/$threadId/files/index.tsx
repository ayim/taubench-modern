import { FilesView } from '~/components/FilesView';
import { useWorkItemQuery } from '~/queries/workItems';
import { createFileRoute } from '@tanstack/react-router';
import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/files/')({
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

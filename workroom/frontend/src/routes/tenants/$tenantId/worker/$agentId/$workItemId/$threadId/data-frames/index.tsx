import { createFileRoute } from '@tanstack/react-router';
import { DataFrameView } from '~/components/DataFrame/View';

import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/data-frames/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { threadId, agentId } = Route.useParams();

  return (
    <Sidebar name="thread-sidebar">
      <DataFrameView agentId={agentId} threadId={threadId} />
    </Sidebar>
  );
}

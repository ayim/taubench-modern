import { FilesView } from '@sema4ai/spar-ui';
import { createFileRoute } from '@tanstack/react-router';

import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/files/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { threadId, agentId } = Route.useParams();

  return (
    <Sidebar name="thread-details">
      <FilesView threadId={threadId} agentId={agentId} />
    </Sidebar>
  );
}

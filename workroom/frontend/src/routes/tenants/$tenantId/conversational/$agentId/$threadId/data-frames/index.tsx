import { createFileRoute } from '@tanstack/react-router';
import { DataFrameView } from '@sema4ai/spar-ui';

import { Sidebar } from '../components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/data-frames/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { threadId, agentId } = Route.useParams();

  return (
    <Sidebar>
      <DataFrameView agentId={agentId} threadId={threadId} />
    </Sidebar>
  );
}

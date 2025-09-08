import { createFileRoute } from '@tanstack/react-router';
import { DataFrameView } from '@sema4ai/spar-ui';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/data-frames/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { threadId, agentId } = Route.useParams();

  return (
    <>
      <span></span>
      <DataFrameView agentId={agentId} threadId={threadId} />
    </>
  );
}

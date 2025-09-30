import { createFileRoute } from '@tanstack/react-router';
import { EvalSidebarView } from '@sema4ai/spar-ui';
import { Sidebar } from '~/components/Sidebar';
import { downloadJSON } from '~/lib/utils';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/evaluations/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId } = Route.useParams();

  return (
    <Sidebar name="thread-sidebar">
      <EvalSidebarView agentId={agentId} onDownloadJSON={downloadJSON} />
    </Sidebar>
  );
}

import { createFileRoute } from '@tanstack/react-router';
import { ConversationGuidesView } from '@sema4ai/spar-ui';
import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/conversation-guides/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId } = Route.useParams();

  return (
    <Sidebar name="Conversation Guides">
      <ConversationGuidesView agentId={agentId} editMode="readOnly" />
    </Sidebar>
  );
}

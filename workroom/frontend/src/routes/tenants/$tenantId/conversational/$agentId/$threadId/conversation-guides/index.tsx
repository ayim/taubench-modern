import { createFileRoute } from '@tanstack/react-router';

import { ConversationGuides } from '~/components/ConversationGuides';
import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/conversation-guides/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId } = Route.useParams();

  return (
    <Sidebar name="thread-sidebar">
      <ConversationGuides agentId={agentId} />
    </Sidebar>
  );
}

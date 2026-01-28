import { createFileRoute } from '@tanstack/react-router';
import { Sidebar } from '~/components/Sidebar';
import { ChatDetails } from '~/components/ChatDetails';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/chat-details/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId } = Route.useParams();

  return (
    <Sidebar name="thread-sidebar">
      <ChatDetails agentId={agentId} />
    </Sidebar>
  );
}

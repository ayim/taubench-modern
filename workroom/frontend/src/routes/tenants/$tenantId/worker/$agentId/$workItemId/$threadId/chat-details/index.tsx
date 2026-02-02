import { ChatDetails } from '~/components/ChatDetails';
import { createFileRoute } from '@tanstack/react-router';
import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/chat-details/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId } = Route.useParams();

  return (
    <Sidebar name="chat-details">
      <ChatDetails agentId={agentId} />
    </Sidebar>
  );
}

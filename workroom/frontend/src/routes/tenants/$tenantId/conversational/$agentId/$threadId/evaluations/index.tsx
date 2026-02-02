import { useEffect } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { EvalSidebarView } from '~/components/Eval/components/EvalSidebarView/EvalSidebarView';
import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/evaluations/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId, threadId, tenantId } = Route.useParams();
  const navigate = useNavigate();

  // Listen for Escape key to close the panel
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        navigate({
          to: '/tenants/$tenantId/conversational/$agentId/$threadId',
          params: { tenantId, agentId, threadId },
        });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [agentId, threadId, tenantId, navigate]);

  return (
    <Sidebar name="thread-sidebar">
      <EvalSidebarView agentId={agentId} />
    </Sidebar>
  );
}

import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { CreateWorkItemDialog } from '@sema4ai/spar-ui';
import { useCallback } from 'react';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/create' as any)({
  component: View,
});

function View() {
  const navigate = useNavigate();
  const { tenantId, agentId } = Route.useParams();

  const handleClose = useCallback(() => {
    navigate({ to: '/tenants/$tenantId/worker/$agentId', params: { tenantId, agentId } });
  }, [navigate, tenantId, agentId]);

  return <CreateWorkItemDialog isOpen={true} onClose={handleClose} agentId={agentId} />;
}

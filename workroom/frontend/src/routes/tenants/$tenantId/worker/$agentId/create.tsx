import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { CreateWorkItemDialog } from '~/components/CreateWorkItemDialog';
import { useCallback } from 'react';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/create')({
  component: View,
});

function View() {
  const navigate = useNavigate();
  const { agentId, tenantId } = Route.useParams();

  const handleClose = useCallback(
    (workItemId?: string) => {
      if (workItemId) {
        navigate({ to: '/tenants/$tenantId/worker/$agentId/$workItemId', params: { tenantId, agentId, workItemId } });
      } else {
        navigate({ to: '..' });
      }
    },
    [navigate, tenantId, agentId],
  );

  return <CreateWorkItemDialog agentId={agentId} isOpen onClose={handleClose} />;
}

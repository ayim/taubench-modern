import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { CreateWorkItemDialog } from '@sema4ai/spar-ui';
import { useCallback } from 'react';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/create')({
  component: View,
});

function View() {
  const navigate = useNavigate();

  const handleClose = useCallback(() => {
    navigate({ to: '..' });
  }, [navigate]);

  return <CreateWorkItemDialog isOpen={true} onClose={handleClose} />;
}

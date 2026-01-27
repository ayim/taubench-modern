import { z } from 'zod';
import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router';
import { AgentDeploymentForm } from '@sema4ai/spar-ui';
import { Box } from '@sema4ai/components';

import { DEFAULT_RUNBOOK, getDefaultAgentTemplate } from '~/constants/agentTemplates';

export const Route = createFileRoute('/tenants/$tenantId/agents/new')({
  component: RouteComponent,
  validateSearch: z.object({
    mode: z.enum(['conversational', 'worker']).optional().catch('conversational'),
  }),
});

function RouteComponent() {
  const { mode = 'conversational' } = Route.useSearch();
  const navigate = useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  const onCancel = () => {
    navigate({ to: '/tenants/$tenantId/home', params: { tenantId } });
  };

  const agentTemplate = getDefaultAgentTemplate(mode);

  return (
    <Box height="100%">
      <Box px="$40" py="$64" maxWidth={768} margin="0 auto">
        <AgentDeploymentForm agentTemplate={agentTemplate} runbook={DEFAULT_RUNBOOK} onCancel={onCancel} />
      </Box>
    </Box>
  );
}

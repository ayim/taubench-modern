import { createFileRoute, useNavigate } from '@tanstack/react-router';

import { EditMcpServerDialog } from '@sema4ai/spar-ui';

export const Route = createFileRoute('/tenants/$tenantId/mcp-servers/$mcpServerId/')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { tenantId, mcpServerId } = Route.useParams();

  return (
    <EditMcpServerDialog
      open
      mcpServerId={mcpServerId}
      onClose={() => navigate({ to: '/tenants/$tenantId/mcp-servers', params: { tenantId } })}
      serverTypes={['generic_mcp']}
    />
  );
}

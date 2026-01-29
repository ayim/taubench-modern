import { createFileRoute } from '@tanstack/react-router';

import { NewMcpServerDialog } from '~/components/MCPServers/MCPServerDialog/NewMcpServerDialog';

export const Route = createFileRoute('/tenants/$tenantId/mcp-servers/new')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = Route.useNavigate();
  const { tenantId } = Route.useParams();

  return (
    <NewMcpServerDialog
      onClose={() => navigate({ to: '/tenants/$tenantId/mcp-servers', params: { tenantId } })}
      open
      serverTypes={['generic_mcp']}
    />
  );
}

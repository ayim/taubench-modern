import { createFileRoute, useParams } from '@tanstack/react-router';
import { NewMcpServerDialog } from '~/components/platforms/mcpServers/components/NewMcpServerDialog';

export const Route = createFileRoute('/tenants/$tenantId/mcp-servers/new')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = Route.useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <NewMcpServerDialog onClose={() => navigate({ to: '/tenants/$tenantId/mcp-servers', params: { tenantId } })} open />
  );
}

import { createFileRoute } from '@tanstack/react-router';
import { NewMcpServerDialog } from '~/components/platforms/mcpServers/components/NewMcpServerDialog';

export const Route = createFileRoute('/tenants/$tenantId/configuration/mcp-servers/new')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = Route.useNavigate();
  const { tenantId } = Route.useParams();

  return (
    <NewMcpServerDialog
      onClose={() => navigate({ to: '/tenants/$tenantId/configuration/mcp-servers', params: { tenantId } })}
      open
    />
  );
}

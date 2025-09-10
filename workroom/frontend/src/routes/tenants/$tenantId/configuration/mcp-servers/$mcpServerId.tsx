import { createFileRoute, useLoaderData, useNavigate } from '@tanstack/react-router';
import { EditMcpServerDialog } from '~/components/platforms/mcpServers/components/EditMcpServerDialog';
import { getMcpServerQueryOptions } from '~/queries/mcpServers';

export const Route = createFileRoute('/tenants/$tenantId/configuration/mcp-servers/$mcpServerId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId, mcpServerId } }) => {
    const data = await queryClient.ensureQueryData(getMcpServerQueryOptions({ agentAPIClient, tenantId, mcpServerId }));
    return data;
  },
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { tenantId } = Route.useParams();
  const initial = useLoaderData({ from: '/tenants/$tenantId/configuration/mcp-servers/$mcpServerId' });

  return (
    <EditMcpServerDialog
      open
      initial={initial}
      onClose={() => navigate({ to: '/tenants/$tenantId/configuration/mcp-servers', params: { tenantId } })}
    />
  );
}

import { createFileRoute, useLoaderData, useNavigate, useParams } from '@tanstack/react-router';
import { EditMcpServerDialog } from '~/components/platforms/mcpServers/components/EditMcpServerDialog';
import { getMcpServerQueryOptions } from '~/queries/mcpServers';

export const Route = createFileRoute('/tenants/$tenantId/mcp-servers/$mcpServerId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId, mcpServerId } }) => {
    const data = await queryClient.ensureQueryData(getMcpServerQueryOptions({ agentAPIClient, tenantId, mcpServerId }));
    return data;
  },
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const initial = useLoaderData({ from: '/tenants/$tenantId/mcp-servers/$mcpServerId' });

  return (
    <EditMcpServerDialog
      open
      initial={initial}
      onClose={() => navigate({ to: '/tenants/$tenantId/mcp-servers', params: { tenantId } })}
    />
  );
}

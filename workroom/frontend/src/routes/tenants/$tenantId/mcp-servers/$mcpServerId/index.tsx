import { createFileRoute, useNavigate } from '@tanstack/react-router';

import { getMcpServerQueryOptions } from '~/queries/mcpServers';
import { EditMcpServerDialog } from '../components/EditMcpServerDialog';

export const Route = createFileRoute('/tenants/$tenantId/mcp-servers/$mcpServerId/')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId, mcpServerId } }) => {
    const data = await queryClient.ensureQueryData(getMcpServerQueryOptions({ agentAPIClient, tenantId, mcpServerId }));
    return data;
  },
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { tenantId } = Route.useParams();
  const initial = Route.useLoaderData();

  return (
    <EditMcpServerDialog
      open
      initial={initial}
      onClose={() => navigate({ to: '/tenants/$tenantId/mcp-servers', params: { tenantId } })}
    />
  );
}

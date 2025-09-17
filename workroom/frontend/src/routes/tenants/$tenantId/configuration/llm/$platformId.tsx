import { createFileRoute, useLoaderData, useNavigate } from '@tanstack/react-router';
import { EditPlatformDialog } from '~/components/platforms/EditPlatformDialog';
import { getPlatformQueryOptions } from '~/queries/platforms';

export const Route = createFileRoute('/tenants/$tenantId/configuration/llm/$platformId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId, platformId } }) => {
    const data = await queryClient.ensureQueryData(getPlatformQueryOptions({ agentAPIClient, tenantId, platformId }));
    return data;
  },
  component: View,
});

function View() {
  const navigate = useNavigate();
  const { tenantId } = Route.useParams();
  const platform = useLoaderData({ from: '/tenants/$tenantId/configuration/llm/$platformId' });

  return (
    <EditPlatformDialog
      platform={platform}
      tenantId={tenantId}
      open
      onClose={() => navigate({ to: '..', params: { tenantId } })}
    />
  );
}

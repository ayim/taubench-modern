import { createFileRoute, useLoaderData, useNavigate } from '@tanstack/react-router';
import { EditPlatformDialog } from '~/components/platforms/EditPlatformDialog';
import { getPlatformQueryOptions, type GetPlatformResponse } from '~/queries/platforms';

export const Route = createFileRoute('/tenants/$tenantId/configuration/llm/$platformId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId, platformId } }) => {
    const data = await queryClient.ensureQueryData(getPlatformQueryOptions({ agentAPIClient, tenantId, platformId }));
    return data;
  },
  component: View,
});

function View() {
  const navigate = useNavigate();
  const { tenantId, platformId } = Route.useParams();
  const platform = useLoaderData({ from: '/tenants/$tenantId/configuration/llm/$platformId' }) as GetPlatformResponse;

  const providerId = String(platform.kind || 'openai').toLowerCase();
  const provider = (['openai', 'azure', 'bedrock'].includes(providerId) ? providerId : 'openai') as
    | 'openai'
    | 'azure'
    | 'bedrock';
  const firstModel = (platform.models?.[providerId] || [])[0];
  const initial = {
    name: platform.name || '',
    provider,
    model: firstModel ? (`${provider}:${firstModel}` as const) : undefined,
  };

  return (
    <EditPlatformDialog
      platformId={platformId}
      open
      initial={initial}
      onClose={() => navigate({ to: '..', params: { tenantId } })}
    />
  );
}

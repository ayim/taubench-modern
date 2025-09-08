import type { paths } from '@sema4ai/agent-server-interface';
import { createFileRoute, useLoaderData, useNavigate, useParams, useRouteContext } from '@tanstack/react-router';
import { EditPlatformDialog } from '~/components/platforms/EditPlatformDialog';

type GetPlatformResponse =
  paths['/api/v2/platforms/{platform_id}']['get']['responses']['200']['content']['application/json'];

export const Route = createFileRoute('/tenants/$tenantId/settings/llm/$platformId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId, platformId } }) => {
    const data = await queryClient.ensureQueryData({
      queryKey: ['platform', tenantId, platformId],
      queryFn: async () => {
        const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/{platform_id}', {
          params: { path: { platform_id: platformId } },
          silent: true,
        });

        if (!response.success) {
          throw new Error(response?.message || 'Failed to fetch platform');
        }

        return response.data;
      },
    });
    return data;
  },
  component: View,
});

function View() {
  const navigate = useNavigate();
  const { tenantId, platformId } = useParams({ from: '/tenants/$tenantId/settings/llm/$platformId' });
  useRouteContext({ from: '/tenants/$tenantId' });
  const platform = useLoaderData({ from: '/tenants/$tenantId/settings/llm/$platformId' }) as GetPlatformResponse;

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

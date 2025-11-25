import { Progress } from '@sema4ai/components';
import { createFileRoute, redirect, useRouteContext } from '@tanstack/react-router';

import { AgentNotFound } from '~/components/AgentNotFound';
import { getVioletAgentQueryOptions } from '~/queries/agents';
import { VioletChatPage, type VioletChatLoaderData } from './violet/VioletChatPage';

export const Route = createFileRoute('/tenants/$tenantId/violet')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId }, location }) => {
    const tenantMeta = await agentAPIClient.getTenantMeta(tenantId);

    // Keep access behind a feature flag; currently mapped to developer mode
    const { features } = tenantMeta ?? {};
    const isEnabled = features?.developerMode?.enabled;

    if (!isEnabled) {
      throw redirect({ to: '/tenants/$tenantId/home', params: { tenantId } });
    }

    const violetAgent = await queryClient.fetchQuery(getVioletAgentQueryOptions({ tenantId, agentAPIClient }));
    const agentId = violetAgent.id ?? (violetAgent as { agent_id?: string }).agent_id;

    if (!agentId) {
      throw new Error('Project violet agent missing id');
    }

    const searchParams = new URLSearchParams(location.search);
    const initialThreadMessage = searchParams.get('initial_thread_message') ?? undefined;

    return { violetAgent, agentId, initialThreadMessage };
  },
  pendingComponent: () => <Progress variant="page" />, // Minimal loading
  errorComponent: AgentNotFound,
  component: VioletChatRoute,
});

function VioletChatRoute() {
  const { tenantId } = Route.useParams();
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const loaderData = Route.useLoaderData() as VioletChatLoaderData;

  return <VioletChatPage tenantId={tenantId} agentAPIClient={agentAPIClient} loaderData={loaderData} />;
}

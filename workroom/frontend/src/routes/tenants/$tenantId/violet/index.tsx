import { z } from 'zod';
import { createFileRoute, redirect, useRouteContext } from '@tanstack/react-router';
import { Progress } from '@sema4ai/components';

import { AgentNotFound } from '~/components/AgentNotFound';
import { useVioletAgentQuery } from '~/queries/violet';
import { VioletChatPage } from './components/VioletChatPage';

export const Route = createFileRoute('/tenants/$tenantId/violet/')({
  loader: async ({ context: { trpc: trpcClient }, params: { tenantId } }) => {
    const tenantConfig = await trpcClient.configuration.getTenantConfig.ensureData();

    if (!tenantConfig.features.developerMode.enabled) {
      throw redirect({ to: '/tenants/$tenantId/home', params: { tenantId } });
    }
  },
  validateSearch: z.object({
    initial_thread_message: z.string().optional(),
  }),
  errorComponent: AgentNotFound,
  component: VioletChatRoute,
});

function VioletChatRoute() {
  const search = Route.useSearch();
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const { data: violetAgent, isLoading } = useVioletAgentQuery({ agentAPIClient });

  if (isLoading) {
    return <Progress variant="page" />;
  }

  const agentId = violetAgent?.id ?? (violetAgent as { agent_id?: string }).agent_id;

  if (!violetAgent || !agentId) {
    return <AgentNotFound />;
  }

  return (
    <VioletChatPage agentId={agentId} violetAgent={violetAgent} initialThreadMessage={search.initial_thread_message} />
  );
}

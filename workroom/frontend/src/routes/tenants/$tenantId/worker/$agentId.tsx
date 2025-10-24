import { Worker } from '@sema4ai/spar-ui';
import { createFileRoute, Link, Outlet } from '@tanstack/react-router';
import { Button } from '@sema4ai/components';
import { getAgentMetaQueryOptions } from '~/queries/agents';
import { AgentMetaContext } from '~/lib/agentMetaContext';
import { EmptyView } from '~/components/EmptyView';
import { Header } from './components/Header';
import { Layout } from './components/Layout';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { agentId, tenantId } }) => {
    const agentMeta = await queryClient.ensureQueryData(
      getAgentMetaQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    return { agentMeta };
  },
  component: RouteComponent,
});

function RouteComponent() {
  const { agentMeta } = Route.useLoaderData();

  if (agentMeta?.workroomUi && !agentMeta.workroomUi.conversations.enabled) {
    return (
      <EmptyView
        title="Conversations are not enabled"
        description={agentMeta.workroomUi.conversations.message}
        illustration="agents"
        docsLink="MAIN_WORKROOM_HELP"
        action={
          <Link to="/">
            <Button forwardedAs="span" round>
              Go to Home
            </Button>
          </Link>
        }
      />
    );
  }

  return (
    <AgentMetaContext.Provider value={agentMeta}>
      <Layout>
        <Header />
        <Worker />
        <Outlet />
      </Layout>
    </AgentMetaContext.Provider>
  );
}

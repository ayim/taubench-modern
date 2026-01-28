import { createFileRoute, Link, Outlet } from '@tanstack/react-router';
import { Button, Progress } from '@sema4ai/components';
import { Worker } from '~/components/Worker';
import { AgentMetaContext } from '~/lib/agentMetaContext';
import { EmptyView } from '~/components/EmptyView';
import { useAgentMetaQuery } from '~/queries/agents';
import { Header } from './components/Header';
import { Layout } from './components/Layout';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId } = Route.useParams();
  const { data: agentMeta, isLoading } = useAgentMetaQuery({ agentId });

  if (isLoading) {
    return <Progress variant="page" />;
  }

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

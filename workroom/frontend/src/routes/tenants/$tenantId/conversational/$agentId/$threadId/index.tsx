import { createFileRoute, Link } from '@tanstack/react-router';
import { Button } from '@sema4ai/components';
import { Thread } from '@sema4ai/spar-ui';

import { EmptyView } from '~/components/EmptyView';
import { TransitionLoader } from '~/components/Loaders';
import { getAgentMetaQueryOptions, getGetAgentQueryOptions } from '~/queries/agents';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { agentId, tenantId } }) => {
    const agent = await queryClient.ensureQueryData(
      getGetAgentQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    const agentMeta = await queryClient.ensureQueryData(
      getAgentMetaQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    return { agent, agentMeta };
  },
  component: View,
  pendingComponent: TransitionLoader,
});

function View() {
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

  return <Thread />;
}

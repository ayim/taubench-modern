import { useMemo, useState } from 'react';
import { createFileRoute, Link, Outlet } from '@tanstack/react-router';
import { useLocalStorage } from '@sema4ai/robocloud-ui-utils';
import { Button } from '@sema4ai/components';

import { EmptyView } from '~/components/EmptyView';
import { TransitionLoader } from '~/components/Loaders';
import { getAgentMetaQueryOptions } from '~/queries/agents';
import { ThreadsUIContext } from './components/ThreadsUIContext';
import { Layout } from './components/Layout';
import { Header } from './components/Header';
import { Thread } from '@sema4ai/spar-ui';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId')({
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
  component: View,
  pendingComponent: TransitionLoader,
});

function View() {
  const { agentMeta } = Route.useLoaderData();

  const { storageValue: threadsExpanded, setStorageValue: setThreadsExpanded } = useLocalStorage<boolean>({
    key: 'chat-conversational-threads-ui',
    defaultValue: false,
    sync: true,
  });
  const [threadsHovered, setThreadsHovered] = useState(false);

  const threadsUIContextValue = useMemo(
    () => ({ threadsExpanded, setThreadsExpanded, threadsHovered, setThreadsHovered }),
    [threadsExpanded, setThreadsExpanded, threadsHovered, setThreadsHovered],
  );

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
    <ThreadsUIContext.Provider value={threadsUIContextValue}>
      <Layout>
        <Header />
        <Thread />
        <Outlet />
      </Layout>
    </ThreadsUIContext.Provider>
  );
}

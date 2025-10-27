import { useMemo, useState } from 'react';
import { createFileRoute, Link, Outlet } from '@tanstack/react-router';
import { useLocalStorage } from '@sema4ai/robocloud-ui-utils';
import { Button, Progress } from '@sema4ai/components';

import { EmptyView } from '~/components/EmptyView';
import { getAgentMetaQueryOptions } from '~/queries/agents';
import { ThreadsUIContext } from './components/ThreadsUIContext';
import { Layout } from './components/Layout';
import { Header } from './components/Header';
import { Thread } from '@sema4ai/spar-ui';
import { AgentMetaContext } from '~/lib/agentMetaContext';
import { getPreferenceKey, setUserPreferenceId } from '~/utils';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { agentId, tenantId, threadId } }) => {
    const agentMeta = await queryClient.ensureQueryData(
      getAgentMetaQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    // Fetch thread data to check if it's an evaluation thread
    const threadResult = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}', {
      params: { path: { tid: threadId } },
    });

    // Only save non-evaluation threads as preferred threads
    // Evaluation threads are identified by having a scenario_id in metadata
    const isEvaluationThread = threadResult.success && threadResult.data.metadata?.scenario_id;
    if (!isEvaluationThread) {
      setUserPreferenceId(getPreferenceKey({ agentId }), threadId);
    }

    return { agentMeta };
  },
  component: View,
  pendingComponent: () => <Progress variant="page" />,
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
    <AgentMetaContext.Provider value={agentMeta}>
      <ThreadsUIContext.Provider value={threadsUIContextValue}>
        <Layout>
          <Header />
          <Thread />
          <Outlet />
        </Layout>
      </ThreadsUIContext.Provider>
    </AgentMetaContext.Provider>
  );
}

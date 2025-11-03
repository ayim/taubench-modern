import { useEffect, useMemo, useState } from 'react';
import { createFileRoute, Link, Outlet, useRouteContext } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useLocalStorage } from '@sema4ai/robocloud-ui-utils';
import { Button, Progress } from '@sema4ai/components';

import { Thread } from '@sema4ai/spar-ui';
import { EmptyView } from '~/components/EmptyView';
import { getAgentMetaQueryOptions } from '~/queries/agents';
import { ThreadsUIContext } from './components/ThreadsUIContext';
import { Layout } from './components/Layout';
import { Header } from './components/Header';
import { AgentMetaContext } from '~/lib/agentMetaContext';
import { getPreferenceKey, setUserPreferenceId } from '~/utils';
import { getThreadQueryOptions } from '~/queries/thread';

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
  pendingComponent: () => <Progress variant="page" />,
});

function View() {
  const { agentMeta } = Route.useLoaderData();
  const { agentId, threadId, tenantId } = Route.useParams();

  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const { data: threadResult, isLoading: isThreadLoading } = useQuery(
    getThreadQueryOptions({ threadId, tenantId, agentAPIClient }),
  );

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

  // Only save non-evaluation threads as preferred threads
  // Evaluation threads are identified by having a scenario_id in metadata
  const isEvaluationThread = Boolean(threadResult?.success && threadResult.data.metadata?.scenario_id);
  useEffect(() => {
    if (!isThreadLoading && !isEvaluationThread) {
      setUserPreferenceId(getPreferenceKey({ agentId }), threadId);
    }
  }, [isEvaluationThread, agentId, threadId, isThreadLoading]);

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

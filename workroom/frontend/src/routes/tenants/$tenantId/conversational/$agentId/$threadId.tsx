import { useEffect, useMemo, useState } from 'react';
import { createFileRoute, Outlet } from '@tanstack/react-router';
import { useLocalStorage } from '@sema4ai/robocloud-ui-utils';

import { useThreadQuery } from '~/queries/threads';
import { Thread } from '~/components/Thread';
import { getPreferenceKey, setUserPreferenceId } from '~/utils';
import { ThreadsUIContext } from './components/ThreadsUIContext';
import { Layout } from './components/Layout';
import { Header } from './components/Header';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId')({
  component: View,
});

function View() {
  const { agentId, threadId } = Route.useParams();
  const { data: thread } = useThreadQuery({ threadId });

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

  useEffect(() => {
    if (!thread) {
      return;
    }
    const isEvaluationThread = Boolean(thread.metadata?.scenario_id);
    if (!isEvaluationThread) {
      setUserPreferenceId(getPreferenceKey({ agentId }), threadId);
    }
  }, [thread]);

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

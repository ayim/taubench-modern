import { useMemo, useState } from 'react';
import { createFileRoute, Outlet } from '@tanstack/react-router';
import { useLocalStorage } from '@sema4ai/robocloud-ui-utils';

import { TransitionLoader } from '~/components/Loaders';
import { ThreadsUIContext } from './components/ThreadsUIContext';
import { Layout } from './components/Layout';
import { Header } from './components/Header';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId')({
  component: View,
  pendingComponent: TransitionLoader,
});

function View() {
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

  return (
    <ThreadsUIContext.Provider value={threadsUIContextValue}>
      <Layout>
        <Header />
        <Outlet />
      </Layout>
    </ThreadsUIContext.Provider>
  );
}

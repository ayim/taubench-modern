import { FC, useEffect, useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useLocalStorage } from '@sema4ai/components';
import { useDataFramesQuery } from '~/queries/dataFrames';
import { useStateTransitionCallback } from '../../../hooks';

const DATA_FRAME_REFETCH_GRACE_PERIOD = 500;
const DATA_FRAME_SIDEBAR_STORAGE_KEY = 'sidebar-thread-sidebar-width';
const DATA_FRAME_SIDEBAR_ID = 'thread-details-sidebar';
const CONVERSATION_SECTION_ID = 'thread-conversation';

const sidebarInitializer = (setSidebarWidth: (width: number) => void): void => {
  const sidebar = document.getElementById(DATA_FRAME_SIDEBAR_ID);
  const sidebarWidth = sidebar?.offsetWidth ?? 0;

  const conversationSection = document.getElementById(CONVERSATION_SECTION_ID);
  if (conversationSection) {
    const targetWidth = Math.floor((conversationSection.offsetWidth + sidebarWidth) * 0.5);
    setSidebarWidth(targetWidth);
  }
};

const DataFrameCallback: FC<{ onComplete: () => void }> = ({ onComplete }) => {
  const { agentId, threadId, workItemId, tenantId } = useParams({ strict: false });

  const { refetch } = useDataFramesQuery({ threadId }, { enabled: false });
  const navigate = useNavigate();

  const { setStorageValue: setSidebarWidth } = useLocalStorage<number>({
    key: DATA_FRAME_SIDEBAR_STORAGE_KEY,
  });

  useEffect(() => {
    setTimeout(() => {
      refetch().then((result) => {
        // Set size only for the first data frame
        if ((result.data ?? []).length === 1) {
          sidebarInitializer(setSidebarWidth);
        }

        if (!workItemId) {
          navigate({
            to: '/tenants/$tenantId/conversational/$agentId/$threadId/data-frames',
            params: { tenantId, agentId, threadId },
          });
        } else {
          navigate({
            to: '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/data-frames',
            params: { tenantId, agentId, workItemId, threadId },
          });
        }

        onComplete();
      });
    }, DATA_FRAME_REFETCH_GRACE_PERIOD);
  }, [refetch, agentId, threadId]);

  return null;
};

export type DataFrameCallbackState = 'in_progress' | 'done' | 'failed';
export const DataFrameCallbackDataFrameCreation: FC<{
  state: DataFrameCallbackState;
}> = ({ state }) => {
  const [triggered, setTriggered] = useState(false);
  const onTransitionTriggered = () => setTriggered(true);
  const onTransitionComplete = () => setTriggered(false);

  useStateTransitionCallback<DataFrameCallbackState>(
    { onTransition: onTransitionTriggered, from: 'in_progress', to: 'done' },
    state,
  );
  if (triggered) return <DataFrameCallback onComplete={onTransitionComplete} />;
  return null;
};

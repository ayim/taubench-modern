import { useSnackbar } from '@sema4ai/components';
import { useCallback } from 'react';

import { useAgentQuery, useCreateThreadMutation, useThreadsQuery } from '../queries';
import { useNavigate } from './useNavigate';
import { useParams } from './useParams';
import { NEW_CHAT_STARTING_MSG } from '../lib/constants';

export const useCreateThread = () => {
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();
  const { agentId } = useParams('/thread/$agentId');
  const { data: threads } = useThreadsQuery({ agentId });
  const { data: agent } = useAgentQuery({ agentId });
  const { mutate: createThread, isPending: isCreatingThread } = useCreateThreadMutation({ agentId });

  const onNewThread = useCallback(async () => {
    const name = threads?.length === undefined ? 'New Chat' : `Chat ${(threads.length || 0) + 1}`;

    const startingMessage = (agent?.extra?.conversation_starter as string | undefined) ?? NEW_CHAT_STARTING_MSG;
    const isUserMessage = !!agent?.extra?.conversation_starter;

    createThread(
      { name, startingMessage, isUserMessage },
      {
        onSuccess: (data) => {
          if (data?.thread_id) {
            navigate({
              to: '/thread/$agentId/$threadId',
              params: { threadId: data.thread_id, agentId },
            });
          }
        },
        onError: () => {
          addSnackbar({
            message: 'Failed to create thread',
            variant: 'danger',
          });
        },
      },
    );
  }, [agent, agentId, threads?.length, createThread, navigate, addSnackbar]);

  return { onNewThread, isCreatingThread };
};

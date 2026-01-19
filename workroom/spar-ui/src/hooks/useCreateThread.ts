import { useSnackbar } from '@sema4ai/components';
import { useCallback } from 'react';

import { useAgentQuery, useAgentOAuthStateQuery, useCreateThreadMutation, useThreadsQuery } from '../queries';
import { useNavigate } from './useNavigate';
import { useParams } from './useParams';
import { NEW_CHAT_STARTING_MSG } from '../lib/constants';

export const useCreateThread = () => {
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();
  const { agentId } = useParams('/thread/$agentId');
  const { data: threads } = useThreadsQuery({ agentId });
  const { data: agent } = useAgentQuery({ agentId });
  const { data: oAuthState = [] } = useAgentOAuthStateQuery({ agentId });
  const { mutate: createThread, isPending: isCreatingThread } = useCreateThreadMutation({ agentId });

  const onNewThread = useCallback(async () => {
    const name = threads?.length === undefined ? 'New Conversation' : `Conversation ${(threads.length || 0) + 1}`;

    const requiresOAuth = oAuthState.some((state) => !state.isAuthorized);

    const isUserMessage = !!agent?.extra?.conversation_starter && !requiresOAuth;
    const startingMessage = isUserMessage ? (agent?.extra?.conversation_starter as string) : NEW_CHAT_STARTING_MSG;

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
  }, [agent, agentId, threads?.length, oAuthState, createThread, navigate, addSnackbar]);

  return { onNewThread, isCreatingThread };
};

import { useSnackbar } from '@sema4ai/components';
import { useCallback } from 'react';
import { useCreateThreadMutation, useThreadsQuery } from '../queries';
import { useNavigate } from './useNavigate';
import { useParams } from './useParams';

export const useCreateThread = () => {
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();
  const { agentId } = useParams('/thread/$agentId');
  const { data: threads } = useThreadsQuery({ agentId });
  const { mutate: createThread, isPending: isCreatingThread } = useCreateThreadMutation({ agentId });

  const onNewThread = useCallback(
    async ({ startingMessage, isUserMessage }: { startingMessage: string; isUserMessage: boolean }) => {
      const name = threads?.length === undefined ? 'New Chat' : `Chat ${(threads.length || 0) + 1}`;
      
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
    },
    [agentId, threads?.length, createThread, navigate, addSnackbar],
  );

  return { onNewThread, isCreatingThread };
};

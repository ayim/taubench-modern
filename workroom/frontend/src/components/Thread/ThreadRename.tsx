import { FC, useMemo } from 'react';
import { useSnackbar } from '@sema4ai/components';
import { useParams } from '@tanstack/react-router';

import { RenameDialog } from '~/components/dialogs/RenameDialog';
import { useThreadsQuery, useUpdateThreadMutation } from '~/queries/threads';

type Props = {
  onClose: () => void;
};

export const ThreadRename: FC<Props> = ({ onClose }) => {
  const { agentId, threadId } = useParams({ strict: false });
  const { data: threads } = useThreadsQuery({ agentId });
  const { mutate: updateThread } = useUpdateThreadMutation({ agentId });
  const { addSnackbar } = useSnackbar();

  const currentName = useMemo(() => {
    const thread = threads?.find((t) => t.thread_id === threadId);
    return thread?.name || '';
  }, [threads, threadId]);

  const onRename = (name: string) => {
    if (!threadId) {
      onClose();
      return;
    }

    updateThread(
      { threadId, name },
      {
        onSuccess: () => {
          addSnackbar({ message: 'Thread renamed successfully', variant: 'success' });
        },
        onError: () => {
          addSnackbar({ message: 'Failed to rename thread', variant: 'danger' });
        },
      },
    );
  };

  return <RenameDialog onClose={onClose} onRename={onRename} entityName={currentName} entityType="Thread" />;
};

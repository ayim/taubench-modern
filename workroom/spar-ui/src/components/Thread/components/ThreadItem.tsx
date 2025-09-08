import { FC, useEffect, useRef, useState } from 'react';
import { styled } from '@sema4ai/theme';
import { Box, Button, Input, Menu, Progress, Typography, useSnackbar } from '@sema4ai/components';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { useConfirmAction } from '@sema4ai/layouts';

import { useNavigate, useParams } from '../../../hooks';
import { useDeleteThreadMutation, useThreadsQuery, useUpdateThreadMutation } from '../../../queries/threads';
import { SidebarLink } from '../../../common/link';

type ThreadItemProps = {
  threadId: string;
  name: string;
};

const Container = styled(Box)<{ $hovered: boolean }>`
  > button {
    display: ${({ $hovered }) => ($hovered ? 'block' : 'none')};
  }

  &:hover {
    > button {
      display: block;
    }
  }
`;

export const ThreadItem: FC<ThreadItemProps> = ({ threadId, name }) => {
  const { agentId, threadId: activeThreadId } = useParams('/conversational/$agentId/$threadId');
  const [menuVisible, setMenuVisible] = useState(false);
  const { mutate: deleteThread, isPending: isDeleting } = useDeleteThreadMutation({ agentId });
  const { mutate: updateThread } = useUpdateThreadMutation({ agentId });
  const { data: threads } = useThreadsQuery({ agentId });
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const [isRenaming, setIsRenaming] = useState(false);
  const [threadName, setThreadName] = useState(name);
  const inputRef = useRef<HTMLInputElement>(null);

  const onDeleteConfirm = useConfirmAction(
    {
      title: 'Delete thread',
      text: 'Are you sure you want to delete this thread?',
      confirmActionText: 'Delete',
    },
    [],
  );

  useEffect(() => {
    if (isRenaming) {
      inputRef.current?.focus();
    }
  }, [isRenaming]);

  const onThreadDelete = onDeleteConfirm(() => {
    deleteThread(
      { threadId },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Thread deleted successfully',
            variant: 'success',
          });

          if (activeThreadId === threadId) {
            const thread = threads?.find((curr) => curr.thread_id !== threadId);
            if (thread?.thread_id) {
              navigate({ to: '/conversational/$agentId/$threadId', params: { threadId: thread.thread_id, agentId } });
            } else {
              navigate({ to: '/conversational/$agentId/home', params: { agentId } });
            }
          }
        },
        onError: () => {
          addSnackbar({
            message: 'Failed to delete thread',
            variant: 'danger',
          });
        },
      },
    );
  });

  const onThreadRename = () => {
    setIsRenaming(false);

    if (threadName !== name) {
      updateThread(
        { threadId, name: threadName },
        {
          onSuccess: () => {
            addSnackbar({
              message: 'Thread renamed successfully',
              variant: 'success',
            });
          },
        },
      );
    }
  };

  if (isRenaming) {
    return (
      <Input
        ref={inputRef}
        aria-label="Thread name"
        value={threadName}
        onChange={(e) => setThreadName(e.target.value)}
        onBlur={onThreadRename}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onThreadRename();
          }
        }}
      />
    );
  }

  return (
    <Container display="flex" justifyContent="space-between" gap="$8" alignItems="center" $hovered={menuVisible}>
      {isDeleting && <Progress variant="page" />}
      <Typography as="span" $nowrap truncate={1}>
        <SidebarLink to="/conversational/$agentId/$threadId" params={{ threadId, agentId }}>
          {name}
        </SidebarLink>
      </Typography>
      <Menu
        visible={menuVisible}
        setVisible={setMenuVisible}
        trigger={<Button variant="ghost-subtle" size="small" icon={IconDotsHorizontal} aria-label="Thread actions" />}
      >
        <Menu.Item onClick={onThreadDelete}>Delete</Menu.Item>
        <Menu.Item onClick={() => setIsRenaming(true)}>Rename</Menu.Item>
      </Menu>
    </Container>
  );
};

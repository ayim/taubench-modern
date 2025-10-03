import { FC, useState } from 'react';
import { Box, Button, Menu, Progress, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import { IconChemicalBottle, IconDotsHorizontal } from '@sema4ai/icons';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';

import { RenameDialog } from '../../../common/dialogs/RenameDialog';
import { formatDateTime } from '../../../common/helpers';
import { SidebarLink } from '../../../common/link';
import { useNavigate, useParams } from '../../../hooks';
import { useDeleteThreadMutation, useThreadsQuery, useUpdateThreadMutation } from '../../../queries/threads';

type ThreadItemProps = {
  threadId: string;
  name: string;
  scenarioId: string | null;
};

const Container = styled(Box)`
  > a {
    overflow: hidden;
    display: block;
    flex: 1;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &:hover > a {
    color: ${({ theme }) => theme.colors.content.primary.color};
  }

  &:has([aria-expanded='true']) {
    > button {
      display: block;
    }
    > a {
      color: ${({ theme }) => theme.colors.content.primary.color};
    }
  }

  &:hover {
    > button {
      display: block;
    }
  }
`;

const ToolTipContent: FC<{ name: string; createdAt?: string }> = ({ name, createdAt }) => {
  return (
    <>
      <Typography fontWeight="medium" mb="$4">
        {name}
      </Typography>
      {createdAt && (
        <Box display="flex">
          Created:
          <Typography ml="$8" fontWeight="medium">
            {formatDateTime(createdAt)}
          </Typography>
        </Box>
      )}
      {/* 
      TODO: add last message time when info is available
      right now we don't have information on last message time
      https://linear.app/sema4ai/issue/CLOUD-5343/feat-last-message-sent 
       */}
      {/* {updatedAt && (
        <Box display="flex">
          Last message:
          <Typography ml="$8" as="span" fontWeight="medium">
            {formatDateTime(updatedAt)}
          </Typography>
        </Box>
      )} */}
    </>
  );
};

export const ThreadItem: FC<ThreadItemProps> = ({ threadId, name, scenarioId }) => {
  const { agentId, threadId: activeThreadId } = useParams('/thread/$agentId/$threadId');
  const { mutate: deleteThread, isPending: isDeleting } = useDeleteThreadMutation({ agentId });
  const { mutate: updateThread } = useUpdateThreadMutation({ agentId });
  const { data: threads } = useThreadsQuery({ agentId });
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const [isRenaming, setIsRenaming] = useState(false);

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: name,
      entityType: 'thread',
    },
    [],
  );

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
              navigate({ to: '/thread/$agentId/$threadId', params: { threadId: thread.thread_id, agentId } });
            } else {
              navigate({ to: '/thread/$agentId', params: { agentId } });
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

  const onThreadRename = (threadName: string) => {
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
  };

  const thread = threads?.find((curr) => curr.thread_id === threadId);

  return (
    <Tooltip text={<ToolTipContent name={name} createdAt={thread?.created_at} />} placement="bottom-end" $nowrap>
      <Container display="flex" justifyContent="space-between" gap="$8" alignItems="center">
        {isDeleting && <Progress variant="page" />}

        <SidebarLink to="/thread/$agentId/$threadId" params={{ threadId, agentId }}>
          <Box display="flex" alignItems="center" gap="$8">
            {scenarioId && <IconChemicalBottle size={20} />}
            {name}
          </Box>
        </SidebarLink>

        <Menu
          trigger={<Button variant="ghost-subtle" size="small" icon={IconDotsHorizontal} aria-label="Thread actions" />}
        >
          <Menu.Item onClick={() => setIsRenaming(true)}>Rename</Menu.Item>
          <Menu.Item onClick={onThreadDelete}>Delete</Menu.Item>
        </Menu>
      </Container>
      {isRenaming && (
        <RenameDialog
          onClose={() => setIsRenaming(false)}
          onRename={onThreadRename}
          entityName={name}
          entityType="Thread"
        />
      )}
    </Tooltip>
  );
};

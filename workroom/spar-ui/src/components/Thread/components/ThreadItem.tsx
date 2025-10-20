import { FC, useState } from 'react';
import { Box, Button, Menu, Progress, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import { IconChemicalBottle, IconDotsHorizontal } from '@sema4ai/icons';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';

import { RenameDialog } from '../../../common/dialogs/RenameDialog';
import { formatDateTime } from '../../../common/helpers';
import { SidebarLink } from '../../../common/link';
import { useNavigate, useParams } from '../../../hooks';
import { ServerResponse } from '../../../queries/shared';
import { useDeleteThreadMutation, useUpdateThreadMutation } from '../../../queries/threads';

type ThreadItemProps = {
  item: ServerResponse<'get', '/api/v2/threads/'>[number] & {
    scenarioId?: string;
  };
};

const Container = styled(Box)`
  > a {
    overflow: hidden;
    display: block;
    flex: 1;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  > button {
    display: none;
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

export const ThreadItem: FC<ThreadItemProps> = ({ item: thread }) => {
  const { agentId, threadId: activeThreadId } = useParams('/thread/$agentId/$threadId');
  const { mutate: deleteThread, isPending: isDeleting } = useDeleteThreadMutation({ agentId });
  const { mutate: updateThread } = useUpdateThreadMutation({ agentId });
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const [isRenaming, setIsRenaming] = useState(false);

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: thread.name,
      entityType: 'thread',
    },
    [],
  );

  const onThreadDelete = onDeleteConfirm(() => {
    deleteThread(
      { threadId: thread.thread_id || '' },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Thread deleted successfully',
            variant: 'success',
          });

          if (activeThreadId === thread.thread_id) {
            navigate({ to: '/thread/$agentId', params: { agentId } });
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
      { threadId: thread.thread_id || '', name: threadName },
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

  return (
    <Tooltip text={<ToolTipContent name={thread.name} createdAt={thread?.created_at} />} placement="bottom-end" $nowrap>
      <Container display="flex" justifyContent="space-between" gap="$8" alignItems="center">
        {isDeleting && <Progress variant="page" />}

        <SidebarLink to="/thread/$agentId/$threadId" params={{ threadId: thread.thread_id || '', agentId }}>
          <Box display="flex" alignItems="center" gap="$8">
            {thread.scenarioId && <IconChemicalBottle size={20} />}
            {thread.name}
          </Box>
        </SidebarLink>

        <Menu
          trigger={<Button variant="ghost-subtle" size="small" icon={IconDotsHorizontal} aria-label="Thread actions" />}
        >
          <Menu.Item onClick={() => setIsRenaming(true)}>Rename</Menu.Item>
          <Menu.Item onClick={onThreadDelete}>Delete</Menu.Item>
        </Menu>
        {isRenaming && (
          <RenameDialog
            onClose={() => setIsRenaming(false)}
            onRename={onThreadRename}
            entityName={thread.name}
            entityType="Thread"
          />
        )}
      </Container>
    </Tooltip>
  );
};

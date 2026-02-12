import { FC, useState, useCallback } from 'react';
import { Box, Button, Menu, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import { IconChemicalBottle, IconDotsHorizontal, IconLoading } from '@sema4ai/icons';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { useNavigate, useParams } from '@tanstack/react-router';

import type { ServerResponse } from '@sema4ai/agent-server-interface';
import { RenameDialog } from '~/components/dialogs/RenameDialog';
import { formatDateTime } from '~/components/helpers';
import { ListItemLink } from '~/components/link';

import { downloadMarkdown } from '~/lib/utils';
import {
  useDeleteThreadMutation,
  useThreadMessagesQuery,
  useUpdateThreadMutation,
  useFetchTraceUrlsMutation,
} from '~/queries/threads';
import { useObservabilityIntegrationsQuery } from '~/queries/integrations';
import { useFeatureFlag, FeatureFlag } from '../../../hooks';
import { ThreadNameDisplay } from './ThreadNameDisplay';
import { getThreadMakrdown } from '../../Chat/utils/threadContentMarkdown';
import { ThreadListLinkContainer } from './ThreadsList/styles';
import { isTraceUrlSupported } from './utils';

type ThreadItemProps = {
  item: ServerResponse<'get', '/api/v2/threads/'>[number] & {
    scenarioId?: string;
  };
};

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
  const { agentId = '', threadId: activeThreadId = '', tenantId = '' } = useParams({ strict: false });
  const { mutate: deleteThread, isPending: isDeleting } = useDeleteThreadMutation({ agentId });
  const { mutate: updateThread, isSuccess: isManualThreadRenameSuccess } = useUpdateThreadMutation({ agentId });
  const { refetch: fetchThreadMessages } = useThreadMessagesQuery({ threadId: activeThreadId }, { enabled: false });
  const { mutate: fetchTraceUrls } = useFetchTraceUrlsMutation({});

  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const [isRenaming, setIsRenaming] = useState(false);
  const { enabled: isChatInteractive } = useFeatureFlag(FeatureFlag.agentChatInput);
  const { data: integrations } = useObservabilityIntegrationsQuery({});

  const supportsTraceUrls = isTraceUrlSupported(integrations);

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
            navigate({ to: '/tenants/$tenantId/conversational/$agentId', params: { agentId, tenantId } });
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
  const onThreadTranscriptDownload = async () => {
    try {
      const messagesResult = await fetchThreadMessages();

      if (messagesResult.error || !Array.isArray(messagesResult.data)) {
        throw new Error('Failed to download');
      }

      const markdownContent = getThreadMakrdown(activeThreadId, messagesResult.data);
      downloadMarkdown(`${activeThreadId}.md`, markdownContent);
    } catch {
      addSnackbar({
        message: 'Failed to download conversation transcript',
        variant: 'danger',
      });
    }
  };

  const handleViewTrace = useCallback(() => {
    fetchTraceUrls(
      { threadId: thread.thread_id || '' },
      {
        onSuccess: (url) => {
          if (url) {
            window.open(url, '_blank');
          } else {
            addSnackbar({
              message: 'No trace URL available for this thread',
              variant: 'default',
            });
          }
        },
        onError: (error) => {
          addSnackbar({
            message: error.message,
            variant: 'danger',
          });
        },
      },
    );
  }, [fetchTraceUrls, addSnackbar, thread.thread_id]);

  const ItemIcon = thread.scenarioId ? IconChemicalBottle : undefined;
  return (
    <>
      <Tooltip
        text={<ToolTipContent name={thread.name} createdAt={thread?.created_at} />}
        placement="bottom-end"
        $nowrap
      >
        <ThreadListLinkContainer>
          <ListItemLink
            to="/tenants/$tenantId/conversational/$agentId/$threadId"
            params={{ threadId: thread.thread_id || '', agentId, tenantId }}
            preserveSubroute
            icon={isDeleting ? IconLoading : ItemIcon}
            hotkey={
              <Menu
                trigger={
                  <Button
                    variant="ghost"
                    size="small"
                    icon={IconDotsHorizontal}
                    aria-label="Thread actions"
                    disabled={!isChatInteractive}
                  />
                }
              >
                <Menu.Item onClick={() => setIsRenaming(true)}>Rename</Menu.Item>
                <Menu.Item onClick={onThreadTranscriptDownload}>Download</Menu.Item>
                {thread.parent_trace_id && supportsTraceUrls && (
                  <Menu.Item onClick={handleViewTrace}>View trace</Menu.Item>
                )}
                <Menu.Item onClick={onThreadDelete}>Delete</Menu.Item>
              </Menu>
            }
          >
            {isManualThreadRenameSuccess ? (
              thread.name
            ) : (
              <ThreadNameDisplay name={thread.name} threadId={thread.thread_id} />
            )}
          </ListItemLink>
        </ThreadListLinkContainer>
      </Tooltip>
      {isRenaming && (
        <RenameDialog
          onClose={() => setIsRenaming(false)}
          onRename={onThreadRename}
          entityName={thread.name}
          entityType="Thread"
        />
      )}
    </>
  );
};

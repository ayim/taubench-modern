import { FC, Fragment, ReactNode, useMemo, useRef } from 'react';
import { ThreadContent, ThreadThoughtContent, ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box, Button, Chat, ChatActionRefType, useSnackbar } from '@sema4ai/components';
import { IconCode } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';

import { snakeCaseToTitleCase } from '~/components/helpers';
import { useFeatureFlag, FeatureFlag, useStateTransitionCallback } from '~/hooks';
import { DataFrameClientTools } from '~/components/DataFrame/tools/Definitions';
import { useShowActionLogsMutation } from '~/queries/agents';
import { ToolCallResult } from '~/components/Chat/components/ToolCallResult';
import { formatThoughtTitle } from './renderer/Thinking';

type ActionState = 'in_progress' | 'done' | 'failed';
type Props = {
  content: ThreadToolUsageContent;
};

const formatGroupTitleDetails = (contentItem?: { name: string }, count = 0) => {
  const contentName = contentItem?.name ? ` ${snakeCaseToTitleCase(contentItem.name)}` : '';
  const contentNameSuffix = count > 1 ? ` and ${count - 1} more` : '';

  return {
    title: contentName,
    optionalSuffix: contentNameSuffix,
  };
};

const getActionState = (
  status: ThreadToolUsageContent['status'],
  contentComplete: ThreadToolUsageContent['complete'],
): ActionState => {
  const isRunning = !contentComplete || ['streaming', 'pending', 'running'].includes(status);
  if (isRunning) return 'in_progress';
  if (status === 'failed') return 'failed';
  return 'done';
};

const getGroupedActions = (messageContent: ThreadContent[]) =>
  messageContent.reduce<{
    inProgress: ThreadToolUsageContent[];
    done: ThreadToolUsageContent[];
    failed: ThreadToolUsageContent[];
    thinking: ThreadThoughtContent[];
    complete: boolean;
  }>(
    (acc, item) => {
      // Check if grouped only items are incomplete
      if (!item.complete && (item.kind === 'thought' || item.kind === 'tool_call')) {
        acc.complete = false;
      }

      if (item.kind === 'thought') {
        acc.thinking.push(item);
      }

      if (item.kind === 'tool_call') {
        const actionState = getActionState(item.status, item.complete);
        switch (actionState) {
          case 'in_progress':
            acc.inProgress.push(item);
            break;
          case 'failed':
            acc.failed.push(item);
            break;
          default:
            acc.done.push(item);
            break;
        }
      }
      return acc;
    },
    { inProgress: [], done: [], failed: [], thinking: [], complete: true },
  );

export const getActionGroupStateDetails = ({
  messageContent,
  messageComplete,
  platform,
  isAdminMode = false,
  hasUnableToSatisfy = false,
}: {
  messageContent: ThreadContent[];
  messageComplete: boolean;
  platform?: string;
  isAdminMode?: boolean;
  hasUnableToSatisfy?: boolean;
}): { state: ActionState; title: string; detailsLabel?: string } => {
  const groupedContent = getGroupedActions(messageContent);
  const lastThinkingItem = groupedContent.thinking[groupedContent.thinking.length - 1];
  const lastContentItem = messageContent[messageContent.length - 1];

  /**
   * To avoid group going from "in progress" to "done" and back to "in progress" when new item is added wait for message to be completed
   * - more common with thinking models where it starts new thought after some action or thought
   */
  const isStreamingFinished = messageComplete && groupedContent.complete;

  const areActionsInProgress = groupedContent.inProgress.length > 0 && !isStreamingFinished;
  const shouldShowThinking = !areActionsInProgress && !isStreamingFinished && lastContentItem?.kind === 'thought';

  if (groupedContent.thinking.length === messageContent.length || shouldShowThinking) {
    return {
      state: isStreamingFinished ? 'done' : 'in_progress',
      title: formatThoughtTitle({ text: lastThinkingItem.thought, platform, complete: isStreamingFinished }),
    };
  }

  if (areActionsInProgress || (!isStreamingFinished && lastContentItem?.kind === 'tool_call')) {
    const runningGroupTitleDetails = formatGroupTitleDetails(
      groupedContent.inProgress[0] || lastContentItem,
      groupedContent.inProgress.length,
    );
    return {
      state: 'in_progress',
      title: `Running ${runningGroupTitleDetails.title} action${runningGroupTitleDetails.optionalSuffix}`,
    };
  }

  if (!isStreamingFinished) {
    return {
      state: 'in_progress',
      title: 'Running',
    };
  }

  // Check if unable_to_satisfy_request was called (passed as parameter since it's hidden from UI)
  if (hasUnableToSatisfy) {
    return {
      state: 'failed',
      title: 'Failed to complete',
    };
  }

  const regularFailures = groupedContent.failed;

  // Only show failure count in details label when in admin mode
  const detailsLabel =
    isAdminMode && regularFailures.length > 0
      ? `Show Details, including ${regularFailures.length} failed tool call${regularFailures.length > 1 ? 's' : ''}`
      : undefined;

  // If there are completed tool calls, show "Completed X action"
  if (groupedContent.done.length > 0) {
    const doneGroupTitleDetails = formatGroupTitleDetails(groupedContent.done[0], groupedContent.done.length);
    return {
      state: 'done',
      title: `Completed ${doneGroupTitleDetails.title} action${doneGroupTitleDetails.optionalSuffix}`,
      detailsLabel,
    };
  }

  // If there are only failures (no done), show thought summary if available
  if (regularFailures.length > 0) {
    if (lastThinkingItem) {
      return {
        state: 'done',
        title: formatThoughtTitle({ text: lastThinkingItem.thought, platform, complete: true }),
        detailsLabel,
      };
    }
    return {
      state: 'done',
      title: 'Completed',
      detailsLabel,
    };
  }

  return {
    state: 'done',
    title: 'Completed',
  };
};

const isActionServerToolCall = (content: ThreadToolUsageContent) => {
  // All existing tool calls made by action server have an action-external sub_type
  // With agent-server >= 2.1.6, action_server_run_id is also surfaced for action-servers (and in the future, by action-server as MCP)

  return (
    content.sub_type === 'action-external' ||
    content.sub_type === 'unknown' || // old action calls had unknown prior to the MCP introduction
    (content.action_server_run_id !== null && content.action_server_run_id !== undefined)
  );
};

export const ToolCall: FC<Props> = ({ content }) => {
  const { agentId = '', threadId = '' } = useParams({ strict: false });
  const { enabled: showActionLogs } = useFeatureFlag(FeatureFlag.showActionLogs);
  const { addSnackbar } = useSnackbar();
  const { mutateAsync, isPending } = useShowActionLogsMutation({});

  const state = getActionState(content.status, content.complete);

  const onShowLogs = async () => {
    await mutateAsync(
      {
        agentId,
        threadId,
        actionServerRunId: content.action_server_run_id ?? null,
        toolCallId: content.tool_call_id,
      },
      {
        onError: (error) =>
          addSnackbar({
            message: error.message,
            variant: error.details?.type === 'notice' ? 'default' : 'danger',
          }),
      },
    );
  };

  return (
    <Fragment key={content.content_id}>
      <Chat.Action
        title={snakeCaseToTitleCase(content.name)}
        running={state === 'in_progress'}
        error={state === 'failed'}
      >
        <ToolCallResult content={content} isDone={state === 'done'} />
        <Box display="flex" gap="$8">
          {showActionLogs && isActionServerToolCall(content) && (
            <Button
              onClick={onShowLogs}
              variant="ghost-subtle"
              icon={IconCode}
              loading={isPending}
              disabled={isPending}
            >
              Show Logs
            </Button>
          )}
        </Box>
      </Chat.Action>
      {DataFrameClientTools.chooseToolToRender(content, state)}
    </Fragment>
  );
};

export const ToolCallGroup: FC<{
  children: ReactNode;
  messageContent: ThreadContent[];
  messageComplete: boolean;
  platform?: string;
  /** Raw message content including hidden tool calls (for detecting unable_to_satisfy_request) */
  rawMessageContent?: ThreadContent[];
}> = ({ children, messageContent, messageComplete, platform, rawMessageContent }) => {
  const groupActionRef = useRef<ChatActionRefType>(null);
  const { enabled: isAdminMode } = useFeatureFlag(SparUIFeatureFlag.adminMode);

  // Check raw content for unable_to_satisfy_request (it's hidden from UI but we need to detect it)
  const hasUnableToSatisfy = useMemo(() => {
    const content = rawMessageContent ?? messageContent;
    return content.some((item) => item.kind === 'tool_call' && item.name === 'unable_to_satisfy_request');
  }, [rawMessageContent, messageContent]);

  const { state, title, detailsLabel } = useMemo(
    () => getActionGroupStateDetails({ messageContent, messageComplete, platform, isAdminMode, hasUnableToSatisfy }),
    [messageContent, messageComplete, platform, isAdminMode, hasUnableToSatisfy],
  );

  const onExpandGroup = () => groupActionRef.current?.setExpanded(true);
  useStateTransitionCallback<typeof state>({ onTransition: onExpandGroup, from: 'in_progress', to: 'failed' }, state);

  return (
    <Chat.Action.Group
      ref={groupActionRef}
      title={title}
      running={state === 'in_progress'}
      error={state === 'failed'}
      detailsLabel={detailsLabel}
    >
      {children}
    </Chat.Action.Group>
  );
};

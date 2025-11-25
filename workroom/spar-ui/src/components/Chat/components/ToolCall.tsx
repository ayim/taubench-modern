import { FC, Fragment, ReactNode, useMemo, useRef } from 'react';
import { ThreadContent, ThreadThoughtContent, ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box, Button, Chat, ChatActionRefType, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconCheck2, IconCode, IconCopy } from '@sema4ai/icons';

import { snakeCaseToTitleCase } from '../../../common/helpers';
import { Code } from '../../../common/code';
import { SparUIFeatureFlag } from '../../../api';
import { useFeatureFlag, useParams, useStateTransitionCallback } from '../../../hooks';
import { DataFrameClientTools } from '../../DataFrame/tools/Definitions';
import { DataFramesQueryOutput } from '../../DataFrame/DataFramesQueryOutput';
import { useShowActionLogsMutation } from '../../../queries';
import { formatThoughtTitle } from './renderer/Thinking';

type ActionState = 'in_progress' | 'done' | 'failed';
type Props = {
  content: ThreadToolUsageContent;
};

const safeParseJson = (text: string | null | undefined) => {
  if (typeof text !== 'string') return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
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

const getActionGroupStateDetails = ({
  messageContent,
  messageComplete,
  platform,
}: {
  messageContent: ThreadContent[];
  messageComplete: boolean;
  platform?: string;
}): { state: ActionState; title: string } => {
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
      title: formatThoughtTitle({ text: lastThinkingItem.thought, platform, complete: lastThinkingItem.complete }),
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

  if (groupedContent.failed.length === 1) {
    const failedGroupTitleDetails = formatGroupTitleDetails(groupedContent.failed[0], groupedContent.failed.length);
    return {
      state: 'failed',
      title: `Failed to complete ${failedGroupTitleDetails.title} action`,
    };
  }

  if (groupedContent.failed.length > 0) {
    return {
      state: 'failed',
      title: 'Failed to complete',
    };
  }

  if (groupedContent.done.length > 0) {
    const doneGroupTitleDetails = formatGroupTitleDetails(groupedContent.done[0], groupedContent.done.length);
    return {
      state: 'done',
      title: `Completed ${doneGroupTitleDetails.title} action${doneGroupTitleDetails.optionalSuffix}`,
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
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { enabled: showActionLogs } = useFeatureFlag(SparUIFeatureFlag.showActionLogs);
  const { onCopyToClipboard: onCopyInput, copiedToClipboard: inputCopied } = useClipboard();
  const { onCopyToClipboard: onCopyOutput, copiedToClipboard: outputCopied } = useClipboard();
  const { addSnackbar } = useSnackbar();
  const { mutateAsync, isPending } = useShowActionLogsMutation({});

  const isError = content.status === 'failed';
  const state = getActionState(content.status, content.complete);

  const input = content.arguments_raw;
  const output = isError ? (content.error ?? content.result) : content.result;

  const toolbar = useMemo(() => {
    return (
      <>
        {input ? (
          <Button
            aria-label="Copy to clipboard"
            variant="inverted"
            size="small"
            icon={inputCopied ? IconCheck2 : IconCopy}
            onClick={onCopyInput(input)}
          >
            Input
          </Button>
        ) : null}
        {output ? (
          <Button
            aria-label="Copy to clipboard"
            variant="inverted"
            size="small"
            icon={outputCopied ? IconCheck2 : IconCopy}
            onClick={onCopyOutput(output)}
          >
            Output
          </Button>
        ) : null}
      </>
    );
  }, [input, output, inputCopied, outputCopied]);

  const result = useMemo(() => {
    const parsedInput = safeParseJson(input);
    const parsedOutput = safeParseJson(output);
    if (!parsedInput && !parsedOutput) return null;
    if (!parsedOutput) return JSON.stringify({ Input: parsedInput }, null, 2);
    return JSON.stringify({ Input: parsedInput, Output: parsedOutput }, null, 2);
  }, [input, output]);

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
        <DataFramesQueryOutput content={content} />
        {result ? <Code title="Tool call" value={result} toolbar={toolbar} lang="json" maxRows={10} /> : null}
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
}> = ({ children, messageContent, messageComplete, platform }) => {
  const groupActionRef = useRef<ChatActionRefType>(null);
  const { state, title } = useMemo(
    () => getActionGroupStateDetails({ messageContent, messageComplete, platform }),
    [messageContent, messageComplete, platform],
  );

  const onExpandGroup = () => groupActionRef.current?.setExpanded(true);
  useStateTransitionCallback<typeof state>({ onTransition: onExpandGroup, from: 'in_progress', to: 'failed' }, state);

  return (
    <Chat.Action.Group ref={groupActionRef} title={title} running={state === 'in_progress'} error={state === 'failed'}>
      {children}
    </Chat.Action.Group>
  );
};

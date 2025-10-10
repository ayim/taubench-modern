import { FC, Fragment, useMemo } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box, Button, Chat, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconCheck2, IconCode, IconCopy } from '@sema4ai/icons';

import { snakeCaseToTitleCase } from '../../../common/helpers';
import { Code } from '../../../common/code';
import { SparUIFeatureFlag } from '../../../api';
import { useFeatureFlag, useParams } from '../../../hooks';
import { DataFrameClientTools } from '../../DataFrame/tools/Definitions';
import { useShowActionLogsMutation } from '../../../queries';

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
  const showActionLogs = useFeatureFlag(SparUIFeatureFlag.showActionLogs);
  const { onCopyToClipboard: onCopyInput, copiedToClipboard: inputCopied } = useClipboard();
  const { onCopyToClipboard: onCopyOutput, copiedToClipboard: outputCopied } = useClipboard();
  const { addSnackbar } = useSnackbar();
  const { mutateAsync, isPending } = useShowActionLogsMutation({});

  const isError = content.status === 'failed';
  const isRunning = ['streaming', 'pending', 'running'].includes(content.status);

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
            variant: 'danger',
          }),
      },
    );
  };

  return (
    <Fragment key={content.content_id}>
      <Chat.Action title={snakeCaseToTitleCase(content.name)} running={isRunning} error={isError}>
        {result ? <Code value={result} toolbar={toolbar} lang="json" maxRows={10} /> : null}
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
      {DataFrameClientTools.chooseToolToRender(content)}
    </Fragment>
  );
};

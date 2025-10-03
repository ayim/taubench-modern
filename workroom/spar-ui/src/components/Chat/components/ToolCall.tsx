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

  const toolbar = useMemo(() => {
    return (
      <>
        <Button
          aria-label="Copy to clipboard"
          variant="inverted"
          size="small"
          icon={inputCopied ? IconCheck2 : IconCopy}
          onClick={onCopyInput(content.arguments_raw)}
        >
          Input
        </Button>
        {content.result && (
          <Button
            aria-label="Copy to clipboard"
            variant="inverted"
            size="small"
            icon={outputCopied ? IconCheck2 : IconCopy}
            onClick={onCopyOutput(content.result)}
          >
            Output
          </Button>
        )}
      </>
    );
  }, [inputCopied, outputCopied]);

  const result = useMemo(() => {
    try {
      const json = JSON.parse(content.result ?? '{}');
      return JSON.stringify(json, null, 2);
    } catch (e) {
      return content.result ?? `{\n}`;
    }
  }, [content]);

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
      <Chat.Action
        actionName={snakeCaseToTitleCase(content.name)}
        running={['streaming', 'pending', 'running'].includes(content.status)}
        error={content.status === 'failed'}
      >
        <Code value={result} toolbar={toolbar} lang="json" maxRows={10} />
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

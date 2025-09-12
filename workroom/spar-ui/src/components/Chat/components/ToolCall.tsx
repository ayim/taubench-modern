import { FC, Fragment, useMemo } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box, Button, Chat, useClipboard, useSnackbar } from '@sema4ai/components';
import { IconCheck2, IconCode, IconCopy } from '@sema4ai/icons';

import { snakeCaseToTitleCase } from '../../../common/helpers';
import { Code } from '../../../common/code';
import { SparUIFeatureFlag } from '../../../api';
import { useFeatureFlag, useParams } from '../../../hooks';
import { useSparUIContext } from '../../../api/context';
import { DataFrameClientTools } from '../../DataFrame/tools/Definitions';

type Props = {
  content: ThreadToolUsageContent;
};

export const ToolCall: FC<Props> = ({ content }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const showActionLogs = useFeatureFlag(SparUIFeatureFlag.showActionLogs);
  const { onCopyToClipboard: onCopyInput, copiedToClipboard: inputCopied } = useClipboard();
  const { onCopyToClipboard: onCopyOutput, copiedToClipboard: outputCopied } = useClipboard();
  const { sparAPIClient } = useSparUIContext();
  const { addSnackbar } = useSnackbar();

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
    const success = await sparAPIClient.openActionLogs?.({ agentId, threadId, toolCallId: content.tool_call_id });
    if (!success) {
      addSnackbar({
        message: 'Unable to open Action Logs',
        variant: 'danger',
      });
    }
  };

  return (
    <Fragment key={content.content_id}>
      <Chat.Action actionName={snakeCaseToTitleCase(content.name)} running={!content.complete}>
        <Code value={result} toolbar={toolbar} lang="json" />
        <Box display="flex" gap="$8">
          {showActionLogs && (
            <Button onClick={onShowLogs} variant="ghost-subtle" icon={IconCode}>
              Show Logs
            </Button>
          )}
        </Box>
      </Chat.Action>
      {DataFrameClientTools.chooseToolToRender(content)}
    </Fragment>
  );
};

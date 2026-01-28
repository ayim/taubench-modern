import { FC, useMemo, useState } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box, Button } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { format as formatSQLQuery } from 'sql-formatter';
import { useParams } from '@tanstack/react-router';

import { Code } from '~/components/code';
import { DATA_FRAME_TOOL_PREFIX } from '../../DataFrame/tools/Definitions';
import { safeParseJson } from '../../../lib/utils';
import { CreateVerifiedQueryFromDataFrameDialog } from '../../DataFrame/CreateVerifiedQueryFromDataFrameDialog';

type Props = {
  content: ThreadToolUsageContent;
  isDone: boolean;
};

export const ToolCallResult: FC<Props> = ({ content, isDone }) => {
  const { agentId = '', threadId = '' } = useParams({ strict: false });
  const [isCreateVerifiedQueryDialogOpen, setIsCreateVerifiedQueryDialogOpen] = useState(false);

  const isError = content.status === 'failed';
  const input = content.arguments_raw;
  const output = isError ? (content.error ?? content.result) : content.result;

  const { dataFrameQuery, dataFrameName } = useMemo(() => {
    const { name, arguments_raw: argumentsRaw } = content;

    const result = {
      dataFrameQuery: '',
      dataFrameName: '',
    };

    if (!name?.startsWith(`${DATA_FRAME_TOOL_PREFIX}`)) {
      return result;
    }

    try {
      const toolCall = JSON.parse(argumentsRaw);
      result.dataFrameQuery = toolCall.sql_query;
      result.dataFrameName = toolCall.new_data_frame_name;
    } catch {
      // do nothing and don't show result on parsing failure
    }

    try {
      result.dataFrameQuery = formatSQLQuery(result.dataFrameQuery);
    } catch {
      // do nothing and don't show query output on parsing failure
    }

    return result;
  }, [content]);

  const { inputContent, outputContent } = useMemo(() => {
    const parsedInput = safeParseJson(input);
    const parsedOutput = safeParseJson(output);
    return {
      inputContent: parsedInput ? JSON.stringify({ Input: parsedInput }, null, 2) : null,
      outputContent: parsedOutput ? JSON.stringify({ Output: parsedOutput }, null, 2) : null,
    };
  }, [input, output]);

  const verifiedQueryToolbar = useMemo(() => {
    return (
      <Box display="flex" gap="$6" justifyContent="center" minWidth={40}>
        {dataFrameName && isDone && (
          <Button
            onClick={() => setIsCreateVerifiedQueryDialogOpen(true)}
            icon={IconPlus}
            variant="ghost-subtle"
            size="small"
          >
            Verified Query
          </Button>
        )}
      </Box>
    );
  }, [dataFrameQuery]);

  return (
    <>
      <Code.Group>
        {dataFrameQuery && (
          <Code open title="Input Query" toolbar={verifiedQueryToolbar} value={dataFrameQuery} lang="sql" maxRows={8} />
        )}
        {inputContent && <Code open={!dataFrameQuery} title="Inputs" value={inputContent} lang="json" maxRows={8} />}
        {outputContent && <Code title="Outputs" value={outputContent} lang="json" maxRows={8} />}
      </Code.Group>
      {isCreateVerifiedQueryDialogOpen && (
        <CreateVerifiedQueryFromDataFrameDialog
          open
          onClose={() => setIsCreateVerifiedQueryDialogOpen(false)}
          threadId={threadId}
          agentId={agentId}
          dataFrameName={dataFrameName}
        />
      )}
    </>
  );
};

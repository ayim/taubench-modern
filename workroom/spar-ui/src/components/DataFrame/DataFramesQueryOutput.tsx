import { FC, useMemo, useState } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box, Button } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { format as formatSQLQuery } from 'sql-formatter';

import { DATA_FRAME_TOOL_PREFIX } from './tools/Definitions';
import { Code } from '../../common/code';
import { useParams } from '../../hooks/useParams';
import { CreateVerifiedQueryFromDataFrameDialog } from './CreateVerifiedQueryFromDataFrameDialog';

type Props = {
  content: ThreadToolUsageContent;
  isDone: boolean;
};

export const DataFramesQueryOutput: FC<Props> = ({ content, isDone }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const [isCreateVerifiedQueryDialogOpen, setIsCreateVerifiedQueryDialogOpen] = useState(false);

  const { query, dataFrameName } = useMemo(() => {
    const { name, arguments_raw: argumentsRaw } = content;

    const result = {
      query: '',
      dataFrameName: '',
    };

    if (!name?.startsWith(`${DATA_FRAME_TOOL_PREFIX}`)) {
      return result;
    }

    try {
      const toolCall = JSON.parse(argumentsRaw);
      result.query = toolCall.sql_query;
      result.dataFrameName = toolCall.new_data_frame_name;
    } catch {
      // do nothing and don't show result on parsing failure
    }

    try {
      result.query = formatSQLQuery(result.query);
    } catch {
      // do nothing and don't show query output on parsing failure
    }

    return result;
  }, [content]);

  const toolbar = useMemo(() => {
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
  }, [query]);

  if (!query) {
    return null;
  }

  return (
    <Box mb="$8">
      <Code title="Input Query" toolbar={toolbar} value={query} lang="sql" />
      {isCreateVerifiedQueryDialogOpen && (
        <CreateVerifiedQueryFromDataFrameDialog
          open
          onClose={() => setIsCreateVerifiedQueryDialogOpen(false)}
          threadId={threadId}
          agentId={agentId}
          dataFrameName={dataFrameName}
        />
      )}
    </Box>
  );
};

import { FC, useMemo } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box } from '@sema4ai/components';
import { format as formatSQLQuery } from 'sql-formatter';

import { DATA_FRAME_TOOL_PREFIX } from './tools/Definitions';
import { Code } from '../../common/code';

type Props = {
  content?: ThreadToolUsageContent;
};

export const DataFramesQueryOutput: FC<Props> = ({ content }) => {
  const query = useMemo(() => {
    if (!content) {
      return null;
    }

    const { name, arguments_raw: argumentsRaw } = content;

    if (!name?.startsWith(`${DATA_FRAME_TOOL_PREFIX}`)) {
      return null;
    }

    try {
      const toolCall = JSON.parse(argumentsRaw);
      return formatSQLQuery(toolCall.sql_query);
    } catch (error) {
      return null;
    }
  }, [content]);

  if (!query) {
    return null;
  }

  return (
    <Box mb="$8">
      <Code title="Input Query" value={query} lang="sql" />
    </Box>
  );
};

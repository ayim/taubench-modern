import { useCallback, useMemo } from 'react';
import { useMessageStream } from '../../../../hooks';

type ValidJSON = unknown;
interface SendResultsToThreadProps {
  results: ValidJSON;
  agentId: string;
  threadId: string;
  fileName: string;
}

const getStringResults = (results: ValidJSON) => {
  try {
    return JSON.stringify(results, null, 2);
  } catch (error) {
    return String(results);
  }
};

const formatResultsForMarkdown = (results: ValidJSON, fileName: string) => {
  return `The following results were extracted from \`${fileName}\`:
\`\`\`sema4di-json
${getStringResults(results)}
\`\`\`
  `;
};

export const useSendResultsToThread = ({ results, agentId, threadId, fileName }: SendResultsToThreadProps) => {
  const { sendMessage } = useMessageStream({
    agentId,
    threadId,
  });

  const sendResultsToThread = useCallback(async () => {
    return sendMessage(
      {
        text: formatResultsForMarkdown(results, fileName),
        type: 'formatted-text',
      },
      [],
    );
  }, [results, fileName, sendMessage]);

  return useMemo(() => {
    if (!results) return { sendResultsToThread: () => Promise.resolve(), enabled: false };
    return { sendResultsToThread, enabled: true };
  }, [sendResultsToThread, results]);
};

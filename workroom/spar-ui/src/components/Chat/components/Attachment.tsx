/* eslint-disable camelcase */
import { ThreadAttachmentContent } from '@sema4ai/agent-server-interface';
import { Box, FileItem } from '@sema4ai/components';
import { useQueryClient } from '@tanstack/react-query';
import { FC, useEffect, useState } from 'react';

import { useSparUIContext } from '../../../api/context';
import { getFileTypeIcon } from '../../../common/helpers';
import { useParams } from '../../../hooks';
import { useAgentQuery, workItemQueryOptions } from '../../../queries';

type Props = {
  content: ThreadAttachmentContent;
};

const AttachmentBase: FC<Props & { threadId: string }> = ({ content: { name, mime_type, description }, threadId }) => {
  const { sparAPIClient } = useSparUIContext();
  const [downloading, setDownloading] = useState(false);

  const onDownload = async () => {
    setDownloading(true);
    await sparAPIClient.downloadFile({ threadId, name });
    setDownloading(false);
  };

  return (
    <Box ml="auto" mb="$8">
      <FileItem
        label={name}
        description={description ?? undefined}
        icon={getFileTypeIcon(mime_type)}
        downloading={downloading}
        onDownloadClick={onDownload}
      />
    </Box>
  );
};

export const Attachment: FC<Props> = ({ content }) => {
  const [threadId, setThreadId] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const { agentId, threadId: possibleThreadId } = useParams('/thread/$agentId/$threadId');
  const { workItemId } = useParams('/workItem/$agentId/$workItemId');

  const { data: agent } = useAgentQuery({ agentId });
  const { sparAPIClient } = useSparUIContext();

  useEffect(() => {
    (async () => {
      if (agent?.metadata?.mode === 'conversational') {
        setThreadId(possibleThreadId);
      } else {
        const workItem = await queryClient.ensureQueryData(workItemQueryOptions({ workItemId, sparAPIClient }));
        setThreadId(workItem.thread_id || null);
      }
    })();
  }, [possibleThreadId, agent?.metadata?.mode, queryClient, workItemId, sparAPIClient]);

  if (!threadId) {
    return null;
  }

  return <AttachmentBase content={content} threadId={threadId} />;
};

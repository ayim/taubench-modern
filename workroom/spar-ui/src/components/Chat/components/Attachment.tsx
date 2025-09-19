/* eslint-disable camelcase */
import { ThreadAttachmentContent } from '@sema4ai/agent-server-interface';
import { Box, FileItem } from '@sema4ai/components';
import { FC, useState } from 'react';

import { useSparUIContext } from '../../../api/context';
import { getFileTypeIcon } from '../../../common/helpers';
import { useParams } from '../../../hooks';

type Props = {
  content: ThreadAttachmentContent;
};

export const Attachment: FC<Props> = ({ content: { name, mime_type, description } }) => {
  const { sparAPIClient } = useSparUIContext();
  const [downloading, setDownloading] = useState(false);

  /**
   * This component can be rendered in either conversational or worker agent.
   * trying to get threadId from both possible routes.
   */
  const { threadId: convThreadId } = useParams('/thread/$agentId/$threadId');
  const { threadId: workerThreadId } = useParams('/workItem/$agentId/$workItemId/$threadId');

  const threadId = convThreadId || workerThreadId;

  if (!threadId) {
    return null;
  }

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

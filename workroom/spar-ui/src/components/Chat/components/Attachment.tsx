/* eslint-disable camelcase */
import { FC, useState } from 'react';
import { Box, FileItem } from '@sema4ai/components';
import { ThreadAttachmentContent } from '@sema4ai/agent-server-interface';

import { getFileTypeIcon } from '../../../common/helpers';
import { useSparUIContext } from '../../../api/context';
import { useParams } from '../../../hooks';

type Props = {
  content: ThreadAttachmentContent;
};

export const Attachment: FC<Props> = ({ content: { name, mime_type, description } }) => {
  const { threadId } = useParams('/thread/$agentId/$threadId');
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

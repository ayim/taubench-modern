/* eslint-disable camelcase */
import { ThreadAttachmentContent } from '@sema4ai/agent-server-interface';
import { Box, FileItem, useSnackbar } from '@sema4ai/components';
import { FC } from 'react';

import { getFileTypeIcon } from '../../../common/helpers';
import { useParams } from '../../../hooks';
import { useDownloadThreadFileMutation } from '../../../queries/threads';
import { getSnackbarContent } from '../../../queries/shared';

type Props = {
  content: ThreadAttachmentContent;
};

export const Attachment: FC<Props> = ({ content: { name, mime_type, description } }) => {
  /**
   * This component can be rendered in either conversational or worker agent.
   * trying to get threadId from both possible routes.
   */
  const { threadId: convThreadId } = useParams('/thread/$agentId/$threadId');
  const { threadId: workerThreadId } = useParams('/workItem/$agentId/$workItemId/$threadId');

  const threadId = convThreadId || workerThreadId;

  const { mutateAsync: downloadFile, isPending: isDownloading } = useDownloadThreadFileMutation({ type: 'download' });
  const { addSnackbar } = useSnackbar();

  if (!threadId) {
    return null;
  }

  const onDownload = async () => {
    await downloadFile(
      { threadId, name },
      {
        onError: (error) => {
          addSnackbar(getSnackbarContent(error));
        },
      },
    );
  };

  return (
    <Box ml="auto" mb="$8">
      <FileItem
        label={name}
        description={description ?? undefined}
        icon={getFileTypeIcon(mime_type)}
        downloading={isDownloading}
        onDownloadClick={onDownload}
      />
    </Box>
  );
};

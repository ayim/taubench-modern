/* eslint-disable camelcase */
import { ThreadAttachmentContent } from '@sema4ai/agent-server-interface';
import { Box, FileItem, useSnackbar } from '@sema4ai/components';
import { FC } from 'react';
import { useParams } from '@tanstack/react-router';

import { getFileTypeIcon } from '~/components/helpers';

import { useDownloadThreadFileMutation } from '~/queries/threads';
import { getSnackbarContent } from '~/queries/shared';

type Props = {
  content: ThreadAttachmentContent;
};

export const Attachment: FC<Props> = ({ content: { name, mime_type, description } }) => {
  const { threadId } = useParams({ strict: false });

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

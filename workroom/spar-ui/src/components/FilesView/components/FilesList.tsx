import { Box, FileItem, Typography } from '@sema4ai/components';
import { IconLoading } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useState } from 'react';

import { useSparUIContext } from '../../../api/context';
import { getFileSize, getFileTypeIcon } from '../../../common/helpers';
import { ThreadFiles, useThreadFilesQuery } from '../../../queries/threads';

type props = {
  threadId: string;
};

const FileListItem = ({ file, threadId }: { file: ThreadFiles[number]; threadId: string }) => {
  const { sparAPIClient } = useSparUIContext();
  const [downloading, setDownloading] = useState(false);

  const onDownload = async () => {
    setDownloading(true);
    await sparAPIClient.downloadFile({ threadId, name: file.file_ref });
    setDownloading(false);
  };
  return (
    <FileItem
      key={file.file_id}
      label={file.file_ref}
      icon={getFileTypeIcon(file.mime_type)}
      description={file.file_size_raw ? getFileSize(file.file_size_raw) : undefined}
      downloading={downloading}
      onDownloadClick={onDownload}
    />
  );
};

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.$16};
  overflow: hidden;
`;

const FilesListContent = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.$12};
  overflow-y: scroll;
`;

export const FilesList: FC<props> = ({ threadId }) => {
  const { data: files, isLoading: isFilesLoading } = useThreadFilesQuery({ threadId });

  if (isFilesLoading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center">
        <IconLoading />
      </Box>
    );
  }

  // Separate files based on work_item_id
  const conversationFiles = files?.filter((file) => !file.work_item_id) || [];
  const workItemFiles = files?.filter((file) => file.work_item_id) || [];

  return (
    <Box display="flex" flexDirection="column" gap={16}>
      {/* Work Item Files Section */}
      {workItemFiles.length > 0 && (
        <Container>
          <Typography variant="body-medium" fontWeight={600}>
            Work Item Files
          </Typography>
          <FilesListContent>
            {workItemFiles.map((file) => (
              <FileListItem file={file} threadId={threadId} key={file.file_id} />
            ))}
          </FilesListContent>
        </Container>
      )}

      {/* Conversation Files Section */}
      {conversationFiles.length > 0 && (
        <Container>
          <Typography variant="body-medium" fontWeight={600}>
            Conversation Files
          </Typography>
          <FilesListContent>
            {conversationFiles.map((file) => (
              <FileListItem file={file} threadId={threadId} key={file.file_id} />
            ))}
          </FilesListContent>
        </Container>
      )}
    </Box>
  );
};

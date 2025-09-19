import { FileItem, Typography } from '@sema4ai/components';
import { IconLoading } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useState } from 'react';

import { useSparUIContext } from '../../../api/context';
import { getFileTypeIcon } from '../../../common/helpers';
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
  return (
    <Container>
      <Typography variant="display-small">Conversation Files</Typography>
      {isFilesLoading && <IconLoading />}
      <FilesListContent>
        {files?.map((file) => (
          <FileListItem file={file} threadId={threadId} key={file.file_id} />
        ))}
      </FilesListContent>
    </Container>
  );
};

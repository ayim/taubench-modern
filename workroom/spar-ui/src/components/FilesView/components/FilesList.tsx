import { Box, Button, FileItem, Typography, useSnackbar } from '@sema4ai/components';
import { IconDocumentIntelligence, IconLoading } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useState, useCallback } from 'react';

import { getFileSize, getFileTypeIcon } from '../../../common/helpers';
import { ThreadFiles, useThreadFilesQuery, useDownloadThreadFileMutation } from '../../../queries/threads';
import { DocumentData, DocumentIntelligenceDialog } from '../../DocumentIntelligence';
import { getSnackbarContent } from '../../../queries/shared';
import { useFeatureFlag } from '../../../hooks/useFeatureFlag';
import { SparUIFeatureFlag } from '../../../api';

type props = {
  threadId: string;
};

const FileListItem = ({
  file,
  threadId,
  onDocumentIntelligenceClick,
}: {
  file: ThreadFiles[number];
  threadId: string;
  onDocumentIntelligenceClick: (params: { file: File; agentId: string }) => void;
}) => {
  const { enabled: shoulDisplayDocIntelButton } = useFeatureFlag(SparUIFeatureFlag.documentIntelligence);

  const { mutateAsync: downloadThreadFile, isPending: isDownloadingThreadFile } = useDownloadThreadFileMutation({
    type: 'download',
  });
  const { mutateAsync: getFileForDocumentIntelligence } = useDownloadThreadFileMutation({ type: 'inline' });
  const { addSnackbar } = useSnackbar();

  const onDownload = async () => {
    await downloadThreadFile(
      { threadId, name: file.file_ref },
      {
        onError: (error) => {
          addSnackbar(getSnackbarContent(error));
        },
      },
    );
  };

  const handleDocIntelClick = useCallback(async () => {
    // This entire logic should be moved to the Doc Intel component that should accept:
    // A file ID, a thread ID and agent ID and eprform this downloadFile
    const downloadedFileResult = await getFileForDocumentIntelligence(
      {
        threadId,
        name: file.file_ref,
      },
      {
        onError: (error) => {
          addSnackbar(getSnackbarContent(error));
        },
      },
    );

    const agentId = file.agent_id;
    if (!agentId) {
      return;
    }

    onDocumentIntelligenceClick({ file: downloadedFileResult.file, agentId });
  }, [
    threadId,
    file.file_ref,
    file.agent_id,
    getFileForDocumentIntelligence,
    onDocumentIntelligenceClick,
    addSnackbar,
  ]);

  return (
    <Box display="flex" alignItems="center">
      <FileItem
        key={file.file_id}
        label={file.file_ref}
        icon={getFileTypeIcon(file.mime_type)}
        description={file.file_size_raw ? getFileSize(file.file_size_raw) : undefined}
        downloading={isDownloadingThreadFile}
        onDownloadClick={onDownload}
      />
      {shoulDisplayDocIntelButton && (
        <Box ml="$8">
          <Button variant="ghost" onClick={handleDocIntelClick}>
            <IconDocumentIntelligence />
          </Button>
        </Box>
      )}
    </Box>
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

  const [docIntelDialogData, setDocIntelDialogData] = useState<DocumentData | null>(null);

  const handleCloseDocIntelDialog = () => {
    setDocIntelDialogData(null);
  };

  const handleOpenDocIntelDialog = (params: { file: File; agentId: string }) => {
    setDocIntelDialogData({
      flowType: 'parse_current_document' as const,
      fileRef: params.file,
      threadId,
      agentId: params.agentId,
      dataModelName: undefined,
    });
  };

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
      {docIntelDialogData && (
        <DocumentIntelligenceDialog
          isOpen={docIntelDialogData !== null}
          onClose={handleCloseDocIntelDialog}
          documentData={docIntelDialogData}
        />
      )}

      {/* Work Item Files Section */}
      {workItemFiles.length > 0 && (
        <Container>
          <Typography variant="body-medium" fontWeight={600}>
            Work Item Files
          </Typography>
          <FilesListContent>
            {workItemFiles.map((file) => (
              <FileListItem
                file={file}
                threadId={threadId}
                key={file.file_id}
                onDocumentIntelligenceClick={handleOpenDocIntelDialog}
              />
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
              <FileListItem
                file={file}
                threadId={threadId}
                key={file.file_id}
                onDocumentIntelligenceClick={handleOpenDocIntelDialog}
              />
            ))}
          </FilesListContent>
        </Container>
      )}
    </Box>
  );
};

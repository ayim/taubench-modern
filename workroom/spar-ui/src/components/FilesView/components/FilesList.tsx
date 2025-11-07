import { Box, Button, FileItem, Menu, Typography, useSnackbar } from '@sema4ai/components';
import { IconDocumentIntelligence, IconLoading } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useCallback } from 'react';

import { getFileSize, getFileTypeIcon } from '../../../common/helpers';
import { ThreadFiles, useThreadFilesQuery, useDownloadThreadFileMutation } from '../../../queries/threads';
import { getSnackbarContent } from '../../../queries/shared';
import { useFeatureFlag } from '../../../hooks/useFeatureFlag';
import { SparUIFeatureFlag } from '../../../api';
import { useAgentDocIntelCapabilities, useDocIntelDialogManager } from '../../DocIntel/shared/hooks';
import { getDocIntelLabel } from '../../DocIntel/shared/constants/interfaceLabels';

type props = {
  agentId: string;
  threadId: string;
};

const FileListItem = ({
  file,
  agentId,
  threadId,
  onDocumentIntelligenceClick,
}: {
  file: ThreadFiles[number];
  agentId: string;
  threadId: string;
  onDocumentIntelligenceClick: (params: { interfaceType: string; file: File; agentId: string }) => void;
}) => {
  const { enabled: docIntelFeatureEnabled } = useFeatureFlag(SparUIFeatureFlag.documentIntelligence);
  const { docIntelInterfaces } = useAgentDocIntelCapabilities(agentId);

  const { mutateAsync: downloadThreadFile, isPending: isDownloadingThreadFile } = useDownloadThreadFileMutation({
    type: 'download',
  });
  const { mutateAsync: getFileForDocumentIntelligence } = useDownloadThreadFileMutation({ type: 'inline' });
  const { addSnackbar } = useSnackbar();

  const isPdfFile = file.mime_type === 'application/pdf' || file.file_ref.toLowerCase().endsWith('.pdf');
  const shouldDisplayDocIntelButton = docIntelFeatureEnabled && docIntelInterfaces.length > 0 && isPdfFile;

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

  const handleDocIntelClick = useCallback(
    async (interfaceType: string) => {
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

      onDocumentIntelligenceClick({
        interfaceType,
        file: downloadedFileResult.file,
        agentId,
      });
    },
    [threadId, file.file_ref, agentId, getFileForDocumentIntelligence, onDocumentIntelligenceClick, addSnackbar],
  );

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
      {shouldDisplayDocIntelButton && (
        <Box
          pl="32px"
          height="46px"
          minHeight="46px"
          marginLeft="-32px"
          display="flex"
          alignItems="center"
          justifyContent="center"
        >
          <Menu
            trigger={
              <Button aria-label="Document Intelligence" variant="ghost-subtle" icon={IconDocumentIntelligence} />
            }
          >
            {docIntelInterfaces.map((interfaceType) => (
              <Menu.Item key={interfaceType} onClick={() => handleDocIntelClick(interfaceType)}>
                {getDocIntelLabel(interfaceType)}
              </Menu.Item>
            ))}
          </Menu>
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
  padding-bottom: ${({ theme }) => theme.space.$8};
  padding-top: ${({ theme }) => theme.space.$8};
`;

export const FilesList: FC<props> = ({ agentId, threadId }) => {
  const { data: files, isLoading: isFilesLoading } = useThreadFilesQuery({ threadId });

  // Use the dialog manager hook - handles dialog state and rendering logic
  const { openDialog, DocIntelDialog } = useDocIntelDialogManager(threadId);

  if (isFilesLoading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center">
        <IconLoading />
      </Box>
    );
  }

  const conversationFiles = files?.filter((file) => !file.work_item_id) || [];
  const workItemFiles = files?.filter((file) => file.work_item_id) || [];

  return (
    <Box display="flex" flexDirection="column" gap={16}>
      <DocIntelDialog />

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
                agentId={agentId}
                threadId={threadId}
                key={file.file_id}
                onDocumentIntelligenceClick={openDialog}
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
                agentId={agentId}
                threadId={threadId}
                key={file.file_id}
                onDocumentIntelligenceClick={openDialog}
              />
            ))}
          </FilesListContent>
        </Container>
      )}
    </Box>
  );
};

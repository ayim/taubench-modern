import { Box, Button, FileItem, Menu, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import { IconDocumentIntelligence, IconLoading } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useCallback } from 'react';

import { getFileSize, getFileTypeIcon } from '../../../common/helpers';
import { ThreadFiles, useThreadFilesQuery, useDownloadThreadFileMutation } from '../../../queries/threads';
import { useDocumentIntelligenceConfigQuery } from '../../../queries/documentIntelligence';
import { getSnackbarContent } from '../../../queries/shared';
import { useFeatureFlag } from '../../../hooks/useFeatureFlag';
import { SparUIFeatureFlag } from '../../../api';
import { useAgentDocIntelCapabilities, useDocIntelDialogManager } from '../../DocIntel/shared/hooks';
import { getDocIntelLabel } from '../../DocIntel/shared/constants/interfaceLabels';

interface ItemProps {
  file: ThreadFiles[number];
  agentId: string;
  threadId: string;
  onDocumentIntelligenceClick: (params: { interfaceType: string; file: File; agentId: string }) => void;
}

const DocumentIntelligenceItem: FC<ItemProps> = ({ file, agentId, threadId, onDocumentIntelligenceClick }) => {
  const { data: docIntelConfig } = useDocumentIntelligenceConfigQuery({});
  const { docIntelInterfaces } = useAgentDocIntelCapabilities(agentId);

  const { mutateAsync: getFileForDocumentIntelligence } = useDownloadThreadFileMutation({ type: 'inline' });
  const { addSnackbar } = useSnackbar();

  /**
   * TODO: this check will fail when we start enforcing permissions on SPAR backend
   * The endpoint currently allows knowledge works to see the config: https://github.com/Sema4AI/agent-platform/blob/72482fff003fc98496e9d4d7b1941a6f3307f7f2/workroom/backend/src/api/routing.ts#L135
   */
  const isDocIntelConfigured = (docIntelConfig?.configuration?.integrations?.length ?? 0) > 0;

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

  if (isDocIntelConfigured) {
    return (
      <Tooltip text="Use document intelligence to analyze this file" placement="top">
        <Menu
          trigger={<Button aria-label="Document Intelligence" variant="ghost-subtle" icon={IconDocumentIntelligence} />}
        >
          {docIntelInterfaces.map((interfaceType) => (
            <Menu.Item key={interfaceType} onClick={() => handleDocIntelClick(interfaceType)}>
              {getDocIntelLabel(interfaceType)}
            </Menu.Item>
          ))}
        </Menu>
      </Tooltip>
    );
  }

  return (
    <Tooltip
      text="Configure Document Intelligence in settings before it can be used to analyze this file"
      placement="top"
    >
      <Button aria-label="Document Intelligence" variant="ghost-subtle" icon={IconDocumentIntelligence} disabled />
    </Tooltip>
  );
};

const ItemAction: FC<ItemProps> = ({ file, agentId, threadId, onDocumentIntelligenceClick }) => {
  const { enabled: docIntelFeatureEnabled } = useFeatureFlag(SparUIFeatureFlag.documentIntelligence);

  const fileName = file.file_ref.toLowerCase();
  const fileExtension = fileName.split('.').pop();
  const mimeType = file.mime_type.toLowerCase();

  const isPdfFile = mimeType === 'application/pdf' || fileExtension === 'pdf';
  const isJsonFile = mimeType === 'application/json' || fileExtension === 'json';

  if (!docIntelFeatureEnabled || isJsonFile) {
    return null;
  }

  return (
    <Box
      pl="32px"
      height="46px"
      minHeight="46px"
      marginLeft="-32px"
      display="flex"
      alignItems="center"
      justifyContent="center"
    >
      {isPdfFile ? (
        <DocumentIntelligenceItem
          file={file}
          agentId={agentId}
          threadId={threadId}
          onDocumentIntelligenceClick={onDocumentIntelligenceClick}
        />
      ) : (
        <Tooltip text="Currently unsupported by Document Intelligence" placement="top">
          <Button aria-label="Document Intelligence" variant="ghost-subtle" icon={IconDocumentIntelligence} disabled />
        </Tooltip>
      )}
    </Box>
  );
};

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
  const { mutateAsync: downloadThreadFile, isPending: isDownloadingThreadFile } = useDownloadThreadFileMutation({
    type: 'download',
  });
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

      <ItemAction
        file={file}
        agentId={agentId}
        threadId={threadId}
        onDocumentIntelligenceClick={onDocumentIntelligenceClick}
      />
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

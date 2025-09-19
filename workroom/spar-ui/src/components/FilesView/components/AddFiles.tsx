import { DropzoneOverlay, Typography } from '@sema4ai/components';
import { IconLoading, IconUpload } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC, useCallback, useMemo } from 'react';
import { DropzoneOptions, useDropzone } from 'react-dropzone';

import { getSupportedExtensions } from '../../../common/helpers';
import { useMessageStream } from '../../../hooks/useMessageStream';
import { useThreadFilesRefetch } from '../../../queries/threads';

type props = {
  agentId: string;
  threadId: string;
  dropzoneOptions?: DropzoneOptions;
};

const Container = styled.button`
  color: inherit;
  background-color: ${({ theme }) => theme.colors.background.panels.color};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  border-radius: ${({ theme }) => theme.radii.$16};
  padding: ${({ theme }) => theme.space.$16};
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.space.$8};
  position: relative;

  &:disabled {
    color: ${({ theme }) => theme.colors.content.subtle.color};
    cursor: not-allowed;
  }
`;

const IconContainer = styled.div`
  width: ${({ theme }) => theme.space.$48};
  height: ${({ theme }) => theme.space.$48};
  background-color: ${({ theme }) => theme.colors.background.accent.light.color};
  border-radius: ${({ theme }) => theme.radii.$24};
  display: flex;
  align-items: center;
  justify-content: center;
`;

export const AddFiles: FC<props> = ({ threadId, agentId, dropzoneOptions }) => {
  const refetchFiles = useThreadFilesRefetch({ threadId });
  const { streamingMessages, uploadingFiles, sendMessage } = useMessageStream({ agentId, threadId });
  const isStreaming = !!streamingMessages;

  const onAddAttachements = useCallback(
    async (files: File[]) => {
      await sendMessage('', files);
    },
    [sendMessage, refetchFiles],
  );

  const {
    getRootProps,
    getInputProps,
    open: onOpenFilePicker,
    isDragActive,
  } = useDropzone({ ...dropzoneOptions, onDrop: onAddAttachements, disabled: uploadingFiles || isStreaming });

  const supportedExtensionsString = useMemo(() => {
    const extensionList = getSupportedExtensions(dropzoneOptions?.accept || {});
    if (extensionList.length === 0) return '';
    return `Supported file extensions: ${extensionList.join(', ')}`;
  }, [dropzoneOptions?.accept]);

  return (
    <Container {...getRootProps()} onClick={onOpenFilePicker} disabled={uploadingFiles || isStreaming}>
      <input {...getInputProps()} />

      {isDragActive ? (
        <DropzoneOverlay />
      ) : (
        <>
          <IconContainer>{uploadingFiles ? <IconLoading /> : <IconUpload />}</IconContainer>
          <Typography variant="display-small">Add Files</Typography>
          <Typography>Upload files to share with your agent</Typography>
          <Typography>{supportedExtensionsString}</Typography>
        </>
      )}
    </Container>
  );
};

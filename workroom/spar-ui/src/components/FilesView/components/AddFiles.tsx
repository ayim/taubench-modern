import { Dropzone, DropzoneConfig } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { FC, useCallback } from 'react';

import { useMessageStream } from '../../../hooks/useMessageStream';
import { useThreadFilesRefetch } from '../../../queries/threads';

type props = {
  agentId: string;
  threadId: string;
  dropzoneOptions?: DropzoneConfig;
};

const AccentText = styled.span<{ disabled: boolean }>`
  color: ${({ theme, disabled }) =>
    disabled ? theme.colors.content.disabled.color : theme.colors.content.accent.color};
`;

export const AddFiles: FC<props> = ({ threadId, agentId, dropzoneOptions }) => {
  const refetchFiles = useThreadFilesRefetch({ threadId });
  const { streamingMessages, uploadingFiles, sendMessage } = useMessageStream({ agentId, threadId });
  const isStreaming = !!streamingMessages;
  const isDisabled = isStreaming || uploadingFiles;

  const onAddAttachements = useCallback(
    async (files: File[]) => {
      await sendMessage('', files);
    },
    [sendMessage, refetchFiles],
  );

  return (
    <Dropzone
      onDrop={onAddAttachements}
      title={
        <span>
          Drag & drop or <AccentText disabled={isDisabled}>select file</AccentText> to upload
        </span>
      }
      disabled={isDisabled}
      dropTitle="Drop your files here"
      multiple
      dropzoneConfig={dropzoneOptions}
    />
  );
};

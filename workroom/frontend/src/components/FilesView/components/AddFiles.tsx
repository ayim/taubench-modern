import { Dropzone as DropzoneBase, DropzoneConfig } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { FC, useCallback } from 'react';

import { FeatureFlag, useFeatureFlag, useMessageStream } from '~/hooks';
import { useThreadFilesRefetch } from '~/queries/threads';
import { useAgentOAuthStateQuery } from '~/queries/agents';

type Props = {
  agentId: string;
  threadId: string;
  dropzoneOptions?: DropzoneConfig;
};

const AccentText = styled.span<{ disabled: boolean }>`
  color: ${({ theme, disabled }) =>
    disabled ? theme.colors.content.disabled.color : theme.colors.content.accent.color};
`;

const Dropzone = styled(DropzoneBase)`
  height: 100%;
`;

export const AddFiles: FC<Props> = ({ threadId, agentId, dropzoneOptions }) => {
  const refetchFiles = useThreadFilesRefetch({ threadId, agentId });
  const { enabled: isChatInteractive } = useFeatureFlag(FeatureFlag.agentChatInput);

  const { streamingMessages, uploadingFiles, sendMessage } = useMessageStream({ agentId, threadId });
  const isStreaming = !!streamingMessages;
  const { data: oAuthState = [] } = useAgentOAuthStateQuery({ agentId });
  const requiresOAuth = oAuthState.some((state) => !state.isAuthorized);

  const isDisabled = isStreaming || uploadingFiles || !isChatInteractive || requiresOAuth;

  const onAddAttachements = useCallback(
    async (files: File[]) => {
      await sendMessage({ text: '' }, files);
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

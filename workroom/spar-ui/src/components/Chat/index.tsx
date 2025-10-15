import {
  Button,
  Chat as ChatComponent,
  ChatInput,
  ChatRef,
  DropzoneOverlay,
  FileItem,
  useSnackbar,
} from '@sema4ai/components';
import { IconPaperclip } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { ClipboardEvent, FC, useEffect, useMemo, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useForm } from 'react-hook-form';

import { getFileSize, getFileTypeIcon, isImageFile } from '../../common/helpers';
import { useMessageStream, useQueryDataGuard } from '../../hooks';
import { useAgentOAuthStateQuery } from '../../queries/agents';
import { useThreadMessagesQuery } from '../../queries/threads';
import { useThreadSearchStore } from '../../state/useThreadSearchStore';
import { OAuth } from './components/OAuth';
import { MessageRenderer } from './components/renderer/Message';

type Props = {
  agentId: string;
  threadId: string;
};

const Container = styled.section`
  position: relative;
  display: grid;
  grid-template-rows: 1fr auto;
  height: 100%;
  min-height: 0;
  flex: 1;
  overflow: hidden;
`;

const Footer = styled.footer`
  width: 100%;
  max-width: 780px;
  margin: 0 auto;
  padding: 0 ${({ theme }) => theme.space.$20} ${({ theme }) => theme.space.$20};
`;

const ChatInputAttachment: FC<{ file: File; onCloseClick: () => void }> = ({ file, onCloseClick }) => {
  const { variant, icon, cleanupAttachmentPreview } = useMemo<
    Pick<React.ComponentProps<typeof FileItem>, 'variant' | 'icon'> & { cleanupAttachmentPreview: () => void }
  >(() => {
    if (isImageFile(file)) {
      const imgSrc = URL.createObjectURL(file);
      return {
        variant: 'image',
        icon: <img src={imgSrc} alt={file.name} />,
        // cleanup function that releases resources of imgSrc
        cleanupAttachmentPreview: () => {
          URL.revokeObjectURL(imgSrc);
        },
      };
    }

    return {
      variant: 'file',
      icon: getFileTypeIcon(file.type),
      cleanupAttachmentPreview: () => {},
    };
  }, [file]);

  const fileSizeText = useMemo(() => getFileSize(file.size), [file.size]);

  useEffect(() => {
    return cleanupAttachmentPreview;
  }, [cleanupAttachmentPreview]);

  return (
    <FileItem
      variant={variant}
      label={file.name}
      description={fileSizeText}
      icon={icon}
      embeded
      onCloseClick={onCloseClick}
    />
  );
};

export const Chat: FC<Props> = ({ agentId, threadId }) => {
  const { addSnackbar } = useSnackbar();
  const chatRef = useRef<ChatRef>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const { currentMessageIndex } = useThreadSearchStore();
  const { data: messages = [], ...threadQueryState } = useThreadMessagesQuery({ threadId });
  const { data: oAuthState = [], ...oauthStateQueryState } = useAgentOAuthStateQuery({ agentId });
  const [attachmentsByThreadId, setAttachmentsByThreadId] = useState<Record<string, File[]>>({});
  const [messageByThreadId, setMessageByThreadId] = useState<Record<string, string>>({});

  const attachments = attachmentsByThreadId[threadId] ?? [];
  const draftMessage = messageByThreadId[threadId] ?? '';

  const onAddAttachments = (files: File[]) => {
    setAttachmentsByThreadId((prevAttachmentsByThread) => {
      const prevThreadAttachments = prevAttachmentsByThread[threadId] ?? [];
      const nameToFile = new Map<string, File>(prevThreadAttachments.map((f) => [f.name, f]));
      files.forEach((file) => nameToFile.set(file.name, file));
      return { ...prevAttachmentsByThread, [threadId]: Array.from(nameToFile.values()) };
    });
  };

  const onRemoveAttachment = (file: File) => {
    setAttachmentsByThreadId((prevAttachmentsByThread) => {
      const prevThreadAttachments = prevAttachmentsByThread[threadId] ?? [];
      return {
        ...prevAttachmentsByThread,
        [threadId]: prevThreadAttachments.filter((f) => f.name !== file.name),
      };
    });
  };

  const {
    getRootProps,
    getInputProps,
    open: onOpenFilePicker,
    isDragActive,
  } = useDropzone({ onDrop: onAddAttachments, noClick: true });

  const { register, handleSubmit, reset, watch } = useForm<{ message: string }>({
    defaultValues: { message: draftMessage },
    shouldUnregister: true,
  });
  const { ref, onChange, ...inputProps } = register('message');
  const onMessageChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e);
    setMessageByThreadId((prevMessagesByThread) => ({
      ...prevMessagesByThread,
      [threadId]: e.target.value,
    }));
  };

  const {
    streamingMessages: allStreamingMessages,
    uploadingFiles,
    sendMessage,
    streamError,
    stopStream,
  } = useMessageStream({
    agentId,
    threadId,
  });

  const streamingMessages = allStreamingMessages?.filter(
    (curr) => !messages.some((message) => message.message_id === curr.message_id),
  );

  const isStreaming = !!streamingMessages?.length;

  const queryDataGuard = useQueryDataGuard([threadQueryState, oauthStateQueryState]);

  const onSubmit = handleSubmit(async ({ message }) => {
    if (!isStreaming) {
      const sendMessageResult = await sendMessage(message, attachments);

      if (!sendMessageResult.success) {
        addSnackbar({ message: sendMessageResult.error.message, variant: 'danger' });
        return;
      }
      setAttachmentsByThreadId((prevAttachmentsByThread) => ({
        ...prevAttachmentsByThread,
        [threadId]: [],
      }));
      setMessageByThreadId((prevMessagesByThread) => ({
        ...prevMessagesByThread,
        [threadId]: '',
      }));
      reset({ message: '' });
    }
  });

  const onAbort = () => {
    stopStream();
    setAttachmentsByThreadId((prevAttachmentsByThread) => ({
      ...prevAttachmentsByThread,
      [threadId]: [],
    }));
    setMessageByThreadId((prevMessagesByThread) => ({
      ...prevMessagesByThread,
      [threadId]: '',
    }));
    reset({ message: '' });
  };

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = Array.from(e.clipboardData?.items || []);

    const files = items
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((f): f is File => f !== null);

    if (files.length > 0) {
      e.preventDefault();
      setAttachmentsByThreadId((prevAttachmentsByThread) => ({
        ...prevAttachmentsByThread,
        [threadId]: files,
      }));
    }
  };

  useEffect(() => {
    if (typeof currentMessageIndex === 'number') {
      chatRef.current?.scrollToIndex(currentMessageIndex);
    }
  }, [currentMessageIndex]);

  useEffect(() => {
    if (!queryDataGuard) {
      chatInputRef.current?.focus();
    }
  }, [threadId, queryDataGuard]);

  useEffect(() => {
    // Ensure the text input reflects the draft for the active thread
    reset({ message: draftMessage });
  }, [threadId, draftMessage, reset]);

  if (queryDataGuard) {
    return queryDataGuard;
  }

  const requiresOAuth = oAuthState.some((state) => !state.isAuthorized);

  const chatInputMessageText = watch('message');
  const hasContentToSend = chatInputMessageText.trim().length > 0 || attachments.length > 0;

  const isStreamingOrUploadingFiles = isStreaming || uploadingFiles;
  const isChatInputBusy = uploadingFiles || (!hasContentToSend && !isStreaming);

  return (
    <Container {...getRootProps()}>
      <ChatComponent
        ref={chatRef}
        messages={messages}
        streamingMessages={streamError ? [streamError] : streamingMessages}
        renderer={MessageRenderer}
      />
      <Footer>
      {requiresOAuth && <OAuth />}
        <ChatInput streaming={isStreamingOrUploadingFiles} busy={isChatInputBusy} onSend={onSubmit} onAbort={onAbort}>
          {attachments.length > 0 && (
            <ChatInput.FileList>
              {attachments.map((file) => (
                <ChatInputAttachment key={file.name} file={file} onCloseClick={() => onRemoveAttachment(file)} />
              ))}
            </ChatInput.FileList>
          )}
          <input {...getInputProps()} />
          <ChatInput.Field
            ref={(e) => {
              ref(e);
              chatInputRef.current = e;
            }}
            {...inputProps}
            onChange={onMessageChange}
            onPaste={onPaste}
            placeholder="Message Agent"
          />
          <ChatInput.Actions>
            <Button
              onClick={onOpenFilePicker}
              icon={IconPaperclip}
              aria-label="Attach file button"
              variant="ghost"
              round
              disabled={isStreamingOrUploadingFiles}
            />
          </ChatInput.Actions>
        </ChatInput>
      </Footer>
      {isDragActive && <DropzoneOverlay />}
    </Container>
  );
};

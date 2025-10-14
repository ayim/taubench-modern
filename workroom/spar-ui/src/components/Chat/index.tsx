import { ClipboardEvent, FC, useEffect, useRef, useState } from 'react';
import {
  Button,
  Chat as ChatComponent,
  ChatInput,
  ChatRef,
  Dialog,
  DropzoneOverlay,
  FileItem,
} from '@sema4ai/components';
import { IconPaperclip } from '@sema4ai/icons';
import { useForm } from 'react-hook-form';
import { styled } from '@sema4ai/theme';
import { useDropzone } from 'react-dropzone';

import { getFileTypeIcon } from '../../common/helpers';
import { useThreadMessagesQuery } from '../../queries/threads';
import { useAgentOAuthStateQuery } from '../../queries/agents';
import { useMessageStream, useQueryDataGuard } from '../../hooks';
import { useThreadSearchStore } from '../../state/useThreadSearchStore';
import { MessageRenderer } from './components/Renderer';
import { OAuth } from './components/OAuth';
import { DocumentIntelligenceView } from '../DocumentIntelligence';

type Props = {
  agentId: string;
  threadId: string;
};

const Container = styled.section`
  position: relative;
  display: grid;
  grid-template-rows: 1fr auto;
  height: calc(100vh - ${({ theme }) => theme.sizes.$64});
`;

const Footer = styled.footer`
  width: 100%;
  max-width: 780px;
  margin: 0 auto;
  padding: 0 ${({ theme }) => theme.space.$20} ${({ theme }) => theme.space.$20};
`;

export const Chat: FC<Props> = ({ agentId, threadId }) => {
  const [documentIntelligenceModalOpen, setDocumentIntelligenceModalOpen] = useState<boolean>(false);
  const chatRef = useRef<ChatRef>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const { currentMessageIndex } = useThreadSearchStore();
  const { data: messages = [], ...threadQueryState } = useThreadMessagesQuery({ threadId });
  const { data: oAuthState = [], ...oauthStateQueryState } = useAgentOAuthStateQuery({ agentId });
  const [attachmentsByThreadId, setAttachmentsByThreadId] = useState<Record<string, File[]>>({});
  const [messageByThreadId, setMessageByThreadId] = useState<Record<string, string>>({});

  const attachments = attachmentsByThreadId[threadId] ?? [];
  const draftMessage = messageByThreadId[threadId] ?? '';

  // Check if any uploaded file has the div2_ prefix - (This is for the Document Intelligence v2 modal TEST)
  const hasDiv2File = attachments.some((file) => file.name.startsWith('div2_'));

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

  const { register, handleSubmit, reset } = useForm<{ message: string }>({
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

  const onSubmit = handleSubmit(({ message }) => {
    if (!isStreaming) {
      sendMessage(message, attachments);
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

  return (
    <Container {...getRootProps()}>
      <ChatComponent
        ref={chatRef}
        messages={messages}
        streamingMessages={streamError ? [streamError] : streamingMessages}
        renderer={MessageRenderer}
      />
      <Footer>
        {hasDiv2File && (
          <Dialog
            trigger={<Button onClick={() => setDocumentIntelligenceModalOpen(true)}>Document Intelligence v2</Button>}
            open={documentIntelligenceModalOpen}
            onClose={() => setDocumentIntelligenceModalOpen(false)}
            size="full-screen"
          >
            <Dialog.Content>
              <DocumentIntelligenceView
                agentId={agentId}
                threadId={threadId}
                flowType="parse"
                fileRef={attachments[0]}
              />
            </Dialog.Content>
          </Dialog>
        )}
        {requiresOAuth && <OAuth />}
        <ChatInput streaming={isStreaming} busy={uploadingFiles} onSend={onSubmit} onAbort={onAbort}>
          {attachments.length > 0 && (
            <ChatInput.FileList>
              {attachments.map((file) => (
                <FileItem
                  key={file.name}
                  label={file.name}
                  icon={getFileTypeIcon(file.type)}
                  embeded
                  onCloseClick={() => onRemoveAttachment(file)}
                />
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
              disabled={isStreaming}
            />
          </ChatInput.Actions>
        </ChatInput>
      </Footer>
      {isDragActive && <DropzoneOverlay />}
    </Container>
  );
};

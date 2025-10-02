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
import { styled } from '@sema4ai/theme';
import { useForm } from 'react-hook-form';
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
  const [attachements, setAttachements] = useState<File[]>([]);

  // Check if any uploaded file has the div2_ prefix - (This is for the Document Intelligence v2 modal TEST)
  const hasDiv2File = attachements.some(file => file.name.startsWith('div2_'));

  const onAddAttachements = (files: File[]) => {
    setAttachements((previousFiles) => {
      const nameToFile = new Map<string, File>(previousFiles.map((f) => [f.name, f]));
      files.forEach((file) => nameToFile.set(file.name, file));
      return Array.from(nameToFile.values());
    });
  };

  const onRemoveAttachement = (file: File) => {
    setAttachements((prev) => prev.filter((f) => f.name !== file.name));
  };

  const {
    getRootProps,
    getInputProps,
    open: onOpenFilePicker,
    isDragActive,
  } = useDropzone({ onDrop: onAddAttachements, noClick: true });

  const { register, handleSubmit, reset } = useForm({
    defaultValues: {
      message: '',
    },
  });
  const { ref, ...inputProps } = register('message');

  const { streamingMessages, uploadingFiles, sendMessage, streamError } = useMessageStream({ agentId, threadId });
  const isStreaming = !!streamingMessages;

  const queryDataGuard = useQueryDataGuard([threadQueryState, oauthStateQueryState]);

  const onSubmit = handleSubmit(({ message }) => {
    if (!isStreaming) {
      sendMessage(message, attachements);
      setAttachements([]);
      reset();
    }
  });

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = Array.from(e.clipboardData?.items || []);

    const files = items
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter(Boolean) as File[];

    if (files.length > 0) {
      e.preventDefault();
      setAttachements(files);
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
                fileRef={attachements[0]}
              />
            </Dialog.Content>
          </Dialog>
        )}
        {requiresOAuth && <OAuth />}
        <ChatInput streaming={isStreaming} busy={uploadingFiles} onSend={onSubmit}>
          {attachements.length > 0 && (
            <ChatInput.FileList>
              {attachements.map((file) => (
                <FileItem
                  key={file.name}
                  label={file.name}
                  icon={getFileTypeIcon(file.type)}
                  embeded
                  onCloseClick={() => onRemoveAttachement(file)}
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

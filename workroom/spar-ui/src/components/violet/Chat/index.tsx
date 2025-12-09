import {
  Banner,
  Box,
  Button,
  Chat as ChatComponent,
  ChatInput,
  ChatRef,
  DropzoneOverlay,
  FileItem,
  useSnackbar,
} from '@sema4ai/components';
import { IconInformation, IconPaperclip } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { ClipboardEvent, FC, useEffect, useMemo, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useForm } from 'react-hook-form';
import { components, ThreadMessage } from '@sema4ai/agent-server-interface';

import { getFileSize, getFileTypeIcon, isImageFile } from '../../../common/helpers';
import { useFeatureFlag, useMessageStream, useQueryDataGuard, useNavigate } from '../../../hooks';
import { useAgentOAuthStateQuery } from '../../../queries/agents';
import { useThreadMessagesQuery } from '../../../queries/threads';
import { useThreadSearchStore } from '../../../state/useThreadSearchStore';
import { OAuth } from './components/OAuth';
import { MessageRenderer } from './components/renderer/Message';
import { ConversationDisabledMessage } from './components/message/ConversationDisabled';
import { SparUIFeatureFlag } from '../../../api';

type Props = {
  agentId: string;
  threadId: string;
  agentType: 'conversational' | 'workItem';
  thread?: components['schemas']['Thread'];
};

const Container = styled.section<{ $hasEvalBanner: boolean }>`
  position: relative;
  display: grid;
  grid-template-rows: ${({ $hasEvalBanner }) => ($hasEvalBanner ? 'auto 1fr auto' : '1fr auto')};
  height: 100%;
  min-height: 0;
  flex: 1;
  overflow: hidden;
`;

const BannerWrapper = styled.div`
  padding: ${({ theme }) => theme.space.$16};
`;

const Footer = styled.footer`
  width: 100%;
  max-width: 980px;
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

export const Chat: FC<Props> = ({ agentId, agentType, threadId, thread }) => {
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const chatRef = useRef<ChatRef>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const { currentMessageIndex } = useThreadSearchStore();
  const [refetchInterval, setRefetchInterval] = useState<number | undefined>(undefined);
  const { data: messages = [], ...threadQueryState } = useThreadMessagesQuery(
    { threadId },
    {
      refetchInterval,
    },
  );
  const { data: oAuthState = [], ...oauthStateQueryState } = useAgentOAuthStateQuery({ agentId });
  const [attachmentsByThreadId, setAttachmentsByThreadId] = useState<Record<string, File[]>>({});
  const [messageByThreadId, setMessageByThreadId] = useState<Record<string, string>>({});

  const chatInputMeta = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const attachments = attachmentsByThreadId[threadId] ?? [];
  const draftMessage = messageByThreadId[threadId] ?? '';

  useEffect(() => {
    // TODO: Refetch thread messages for WorkItems if no agent response has been received yet
    // This should be removed once we have a way to determine if a stream for a thread is active and listen to it
    if (agentType === 'workItem') {
      setRefetchInterval(messages.filter((message) => message.role === 'agent').length === 0 ? 3000 : undefined);
    }
  }, [messages]);

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

  const streamingMessages = (() => {
    if (allStreamingMessages) {
      return allStreamingMessages?.filter(
        (curr) => !messages.some((message) => message.message_id === curr.message_id),
      );
    }

    // TODO: Refetch thread messages for WorkItems if no agent response has been received yet
    // This should be removed once we have a way to determine if a stream for a thread is active and listen to it
    if (agentType === 'workItem' && messages.filter((message) => message.role === 'agent').length === 0) {
      return [
        {
          message_id: 'initial-agent-response',
          role: 'agent',
          content: [
            {
              kind: 'thought',
              complete: false,
              thought: '',
            },
          ],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          complete: false,
          commited: false,
        } satisfies ThreadMessage,
      ];
    }

    return undefined;
  })();

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
  }, [threadId, queryDataGuard, attachments.length]);

  useEffect(() => {
    // Ensure the text input reflects the draft for the active thread
    reset({ message: draftMessage });
  }, [threadId, draftMessage, reset]);

  const requiresOAuth = oAuthState.some((state) => !state.isAuthorized);

  const handleExitEvaluation = () => {
    // Clear the preferred thread preference so we don't come back to this eval thread
    const preferenceKey = `preffered-thread-or-work-item-${agentId}`;
    localStorage.removeItem(preferenceKey);

    navigate({
      to: '/thread/$agentId',
      params: { agentId },
    });
  };

  const chatInputMessageText = watch('message');
  const hasContentToSend = chatInputMessageText.trim().length > 0 || attachments.length > 0;

  const docIntLocked = useMemo(() => {
    const combined: ThreadMessage[] = [...messages, ...((streamingMessages as ThreadMessage[] | undefined) ?? [])];
    for (let i = combined.length - 1; i >= 0; i -= 1) {
      const msg = combined[i];
      if (msg.role === 'agent') {
        const metadata = msg.agent_metadata as { doc_int_input_locked?: boolean } | undefined;
        const locked = metadata?.doc_int_input_locked;
        if (locked === true) return true;
        if (locked === false) return false;
      }
    }
    return false;
  }, [messages, streamingMessages]);

  let chatDisabledReason: string | undefined;
  if (!chatInputMeta.enabled) {
    chatDisabledReason = chatInputMeta.message;
  } else if (docIntLocked) {
    chatDisabledReason = 'Complete PDF markup to continue.';
  }

  const isStreamingOrUploadingFiles = isStreaming || uploadingFiles;
  const isChatInputBusy = uploadingFiles || (!hasContentToSend && !isStreaming);
  const isChatInputDisabled = requiresOAuth || Boolean(chatDisabledReason);
  const isAttachFileBtnDisabled = isStreamingOrUploadingFiles || isChatInputDisabled;

  const {
    getRootProps,
    getInputProps,
    open: onOpenFilePicker,
    isDragActive,
  } = useDropzone({ onDrop: onAddAttachments, noClick: true, disabled: isAttachFileBtnDisabled });

  if (queryDataGuard) {
    return queryDataGuard;
  }

  const isEvaluationThread = Boolean(thread?.metadata?.scenario_id);
  const evaluationError = thread?.metadata?.evaluation_error as string | undefined;

  return (
    <Container
      {...getRootProps()}
      $hasEvalBanner={isEvaluationThread}
      key={`chat-${threadId}`}
      id="thread-conversation"
    >
      {isEvaluationThread && (
        <BannerWrapper>
          <Banner
            message={thread?.name || 'Evaluation Results'}
            description="This is a saved evaluation thread with agent responses and tool usage."
            icon={IconInformation}
            variant="info"
          >
            <Box display="flex" alignItems="center">
              <Button size="small" variant="outline" onClick={handleExitEvaluation}>
                Exit Evaluation
              </Button>
            </Box>
          </Banner>
        </BannerWrapper>
      )}
      <ChatComponent
        ref={chatRef}
        messages={messages}
        streamingMessages={streamError ? [streamError] : streamingMessages}
        renderer={MessageRenderer}
      />
      {isEvaluationThread && evaluationError && (
        <BannerWrapper>
          <Banner message={evaluationError} icon={IconInformation} variant="error" />
        </BannerWrapper>
      )}
      {!isEvaluationThread && (
        <Footer>
          {requiresOAuth && <OAuth />}
          {chatDisabledReason && <ConversationDisabledMessage reason={chatDisabledReason} />}
          <ChatInput
            streaming={isStreamingOrUploadingFiles}
            busy={isChatInputBusy}
            onSend={onSubmit}
            onAbort={onAbort}
            disabled={isChatInputDisabled}
          >
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
                disabled={isAttachFileBtnDisabled}
              />
            </ChatInput.Actions>
          </ChatInput>
        </Footer>
      )}
      {isDragActive && <DropzoneOverlay />}
    </Container>
  );
};

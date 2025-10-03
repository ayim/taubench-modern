import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Banner, Box, Button, Chat, useClipboard } from '@sema4ai/components';
import { IconAlert, IconCheck2, IconCopy, IconThumbsDown } from '@sema4ai/icons';
import MarkJS from 'mark.js';
import { FC, useEffect, useRef } from 'react';

import { styled } from '@sema4ai/theme';
import { useSparUIContext } from '../../../api/context';
import { useToggle } from '../../../hooks/useToggle';
import { AgentErrorStreamPayload } from '../../../lib/AgentServerTypes';
import { useThreadSearchStore } from '../../../state/useThreadSearchStore';
import { Attachment } from './Attachment';
import { FeedbackDialog } from './FeedbackDialog';
import { markdownRules } from './markdown';
import { ToolCall } from './ToolCall';
import { useFeatureFlag } from '../../../hooks/useFeatureFlag';
import { SparUIFeatureFlag } from '../../../api';

type Props = {
  message: ThreadMessage | AgentErrorStreamPayload;
  streaming: boolean;
};

const MessageContainer = styled(Box)`
  &:hover .message-actions {
    opacity: 1;
    visibility: visible;
  }
`;

const MessageActions = styled(Box)`
  opacity: 0;
  visibility: hidden;
  transition:
    opacity 0.2s ease-in-out,
    visibility 0.2s ease-in-out;
  display: flex;
  justify-content: flex-end;
  gap: $4;
`;

const groupTitleMap = {
  'done': 'Completed tasks',
  'in_progress': 'Working on it',
  'failed': 'Failed tasks',
} as const;

const getGroupeStatus = ({ message }: {message: ThreadMessage }): keyof typeof groupTitleMap => {
  const messageStatus = message.complete ? 'done' : 'in_progress';
  if (messageStatus === 'done') {
    const failedIndex = message.content.findIndex(item => item.kind === 'tool_call' && item.status === 'failed');
    if (failedIndex !== -1) {
      return 'failed';
    }
  }
  return messageStatus;
}

type ThreadMessageContent = ThreadMessage['content'];
const getGroupedMessageContent = (messageContent: ThreadMessageContent) => messageContent.reduce<(ThreadMessageContent | ThreadMessageContent[number])[]>((acc, content) => {
    if (['thought', 'tool_call'].includes(content.kind)) {
      const previousContent = acc[acc.length - 1];
      if (Array.isArray(previousContent)) {
        previousContent.push(content);
        return acc;
      }

      acc.push([content]);
      return acc;
    }

    acc.push(content);
    return acc;
  }, []).map(content => Array.isArray(content) && content.length === 1 ? content[0] : content);

export const MessageRenderer: FC<Props> = ({ message, streaming }) => {
  const { query } = useThreadSearchStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();
  const { val: isFeedbackDialogOpen, setTrue: openFeedbackDialog, setFalse: closeFeedbackDialog } = useToggle();
  const { sparAPIClient } = useSparUIContext();
  const feedbackEnabled = useFeatureFlag(SparUIFeatureFlag.showFeedback);
  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const markInstance = new MarkJS(containerRef.current);
    markInstance.unmark({
      done: () => {
        markInstance.mark(query, {
          acrossElements: true,
          separateWordSearch: false,
          done: () => {
            const elements = Array.from(containerRef.current?.getElementsByTagName('mark') || []);
            if (elements.length) {
              elements[0].scrollIntoView({ block: 'center' });
            }
          },
        });
      },
    });
  }, [query]);

  // TODO-V2: Styling of a stream error
  if ('error_id' in message) {
    return <Banner message="An error occurred" description={message.message} icon={IconAlert} variant="error" />;
  }

  const messageContent = message.content ?? [];
  const contentRenderer = (content: typeof messageContent[number]) => {
    switch (content.kind) {
      case 'thought':
        return (
          <Chat.Thinking streaming={streaming} key={content.content_id} title={!streaming && content.complete ? 'Thought' : undefined}>
            {content.thought}
          </Chat.Thinking>
        );
      case 'text':
        if (message.role === 'user') {
          return (
            <Chat.UserMessage ref={containerRef} key={content.content_id}>
              {content.text}
            </Chat.UserMessage>
          );
        }

        return (
          <MessageContainer key={content.content_id}>
            <Chat.Markdown
              ref={containerRef}
              messageId={message.message_id}
              streaming={streaming}
              parserRules={markdownRules}
            >
              {content.text}
            </Chat.Markdown>
            <MessageActions className="message-actions">
              <Button
                icon={copiedToClipboard ? IconCheck2 : IconCopy}
                onClick={onCopyToClipboard(content.text)}
                aria-label="Copy to clipboard"
                variant="ghost-subtle"
                size="small"
              />
              {feedbackEnabled && sparAPIClient.sendFeedback && (
                <Button
                  icon={IconThumbsDown}
                  onClick={() => openFeedbackDialog()}
                  aria-label="Feedback"
                  variant="ghost-subtle"
                  size="small"
                />
              )}
            </MessageActions>
            {isFeedbackDialogOpen && feedbackEnabled && sparAPIClient.sendFeedback && (
              <FeedbackDialog open={isFeedbackDialogOpen} onClose={closeFeedbackDialog} />
            )}
          </MessageContainer>
        );
      case 'tool_call':
        return <ToolCall key={content.content_id} content={content} />;
      case 'attachment':
        return <Attachment key={content.content_id} content={content} />;
      default:
        return null;
    }
  }

  const groupedMessageContent = getGroupedMessageContent(messageContent);
  return groupedMessageContent.map((content) => {
    if (Array.isArray(content)) {
      const messageStatus = getGroupeStatus({message});
      return  (
        <Chat.Action.Group title={groupTitleMap[messageStatus]} running={messageStatus === 'in_progress'} error={messageStatus === 'failed'} key={`group-${content[0].content_id}`}>
          {content.map((itemContent) => contentRenderer(itemContent))}
        </Chat.Action.Group>
      );
    }
    return contentRenderer(content);
  });
};

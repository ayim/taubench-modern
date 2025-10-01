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

  return message.content?.map((content) => {
    switch (content.kind) {
      case 'thought':
        return (
          <Chat.Thinking streaming={streaming} key={content.content_id}>
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
          <MessageContainer>
            <Chat.Markdown
              ref={containerRef}
              messageId={message.message_id}
              streaming={streaming}
              parserRules={markdownRules}
              key={content.content_id}
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
  });
};

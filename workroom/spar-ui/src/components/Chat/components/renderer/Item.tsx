import { FC, useEffect, useRef } from 'react';
import MarkJS from 'mark.js';
import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Box, Button, Chat, useClipboard } from '@sema4ai/components';
import { IconCheck2, IconCopy, IconThumbsDown } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';

import { Attachment } from '../Attachment';
import { FeedbackDialog } from '../FeedbackDialog';
import { markdownRules } from '../markdown';
import { ToolCall } from '../ToolCall';
import { useSparUIContext } from '../../../../api/context';
import { useToggle } from '../../../../hooks/useToggle';
import { useThreadSearchStore } from '../../../../state/useThreadSearchStore';
import { useFeatureFlag } from '../../../../hooks/useFeatureFlag';
import { SparUIFeatureFlag } from '../../../../api';
import { Thinking } from './Thinking';

type Props = {
  message: ThreadMessage;
  /**
   * Preprocessed content item of message, preprocessing includes:
   * - grouping similar actions
   */
  messageContentItem: ThreadMessage['content'][number];
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

const TOOL_CALLS_TO_IGNORE: Record<string, boolean> = {
  quick_reply: true,
  consider_runbook_adherence: true,
  ready_to_reply_to_user: true,
  unable_to_satisfy_request: true,
};
export const shouldIgnoreToolCall = (toolCallName: string) => TOOL_CALLS_TO_IGNORE[toolCallName] === true;

export const MessageContentItemRenderer: FC<Props> = ({ message, messageContentItem: content, streaming }) => {
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

  switch (content.kind) {
    case 'thought': {
      const isThinkingDone = content.complete;
      const messagePlatform = message.agent_metadata?.platform;
      return (
        <Thinking
          key={content.content_id}
          complete={isThinkingDone}
          platform={typeof messagePlatform === 'string' ? messagePlatform : undefined}
        >
          {content.thought}
        </Thinking>
      );
    }
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
      /**
       * Skip internal tool calls that don't bring value to the user
       */
      if (shouldIgnoreToolCall(content.name)) return null;
      return <ToolCall key={content.content_id} content={content} />;
    case 'attachment':
      return <Attachment key={content.content_id ?? content.name} content={content} />;
    default:
      return null;
  }
};

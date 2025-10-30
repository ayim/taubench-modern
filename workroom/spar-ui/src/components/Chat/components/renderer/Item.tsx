import { FC, useEffect, useRef } from 'react';
import MarkJS from 'mark.js';
import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Box, Button, Chat, useClipboard } from '@sema4ai/components';
import { IconBallotBox, IconCheck2, IconCopy } from '@sema4ai/icons';
import { css, styled } from '@sema4ai/theme';

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
  platform?: string;
  isLastMessage?: boolean;
  isFirstMessage?: boolean;
  isLastContentItem?: boolean;
};

const MessageContainer = styled(Box)`
  &:hover .message-actions {
    opacity: 1;
    visibility: visible;
  }
`;

const otherMessageActionsCss = css`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
`;

const MessageActions = styled(Box)<{ $isLastMessage?: boolean; $isLastContentItem?: boolean }>`
  position: relative;
  padding-bottom: ${({ $isLastMessage, $isLastContentItem, theme }) =>
    !$isLastMessage && $isLastContentItem ? theme.space.$4 : 0};

  > div {
    opacity: ${({ $isLastMessage }) => ($isLastMessage ? 1 : 0)};
    transition: opacity 0.2s ease-in-out 0.4s;
    display: flex;
    justify-content: flex-start;
    gap: ${({ theme }) => theme.space.$4};
    margin-left: -${({ theme }) => theme.space.$8};
    ${({ $isLastMessage, $isLastContentItem }) => !$isLastMessage && $isLastContentItem && otherMessageActionsCss}
  }
`;

const TOOL_CALLS_TO_IGNORE: Record<string, boolean> = {
  quick_reply: true,
  consider_runbook_adherence: true,
  ready_to_reply_to_user: true,
  unable_to_satisfy_request: true,
};
export const shouldIgnoreToolCall = (toolCallName: string) => TOOL_CALLS_TO_IGNORE[toolCallName] === true;

export const MessageContentItemRenderer: FC<Props> = ({
  message,
  messageContentItem: content,
  streaming,
  platform,
  isLastMessage,
  isFirstMessage,
  isLastContentItem,
}) => {
  const { query } = useThreadSearchStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();
  const { val: isFeedbackDialogOpen, setTrue: openFeedbackDialog, setFalse: closeFeedbackDialog } = useToggle();
  const { sparAPIClient } = useSparUIContext();
  const { enabled: feedbackEnabled } = useFeatureFlag(SparUIFeatureFlag.agentFeedback);
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
      return (
        <Thinking key={content.content_id} complete={isThinkingDone} platform={platform}>
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
          <MessageActions
            $isLastMessage={isLastMessage && !isFirstMessage && !streaming}
            $isLastContentItem={isLastContentItem}
          >
            <div className="message-actions">
              <Button
                icon={copiedToClipboard ? IconCheck2 : IconCopy}
                onClick={onCopyToClipboard(content.text)}
                aria-label="Copy to clipboard"
                variant="ghost-subtle"
              />
              {feedbackEnabled && sparAPIClient.sendFeedback && (
                <Button
                  icon={IconBallotBox}
                  onClick={() => openFeedbackDialog()}
                  aria-label="Feedback"
                  variant="ghost-subtle"
                />
              )}
            </div>
          </MessageActions>
          {isFeedbackDialogOpen && <FeedbackDialog open onClose={closeFeedbackDialog} />}
        </MessageContainer>
      );
    case 'tool_call':
      return <ToolCall key={content.content_id} content={content} />;
    case 'attachment':
      return <Attachment key={content.content_id ?? content.name} content={content} />;
    default:
      return null;
  }
};

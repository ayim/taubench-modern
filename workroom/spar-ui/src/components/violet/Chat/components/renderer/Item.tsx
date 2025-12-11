import { FC, useEffect, useRef } from 'react';
import MarkJS from 'mark.js';
import type { ThreadMessage, ThreadQuickActionsContent, ThreadVegaChartContent } from '@sema4ai/agent-server-interface';
import { Box, Button, Chat, useClipboard } from '@sema4ai/components';
import { IconBallotBox, IconCheck2, IconCopy } from '@sema4ai/icons';
import { css, styled } from '@sema4ai/theme';

import { Attachment } from '../Attachment';
import { FeedbackDialog } from '../FeedbackDialog';
import { createMarkdownRules, type InlineWidget } from '../markdown';
import { ToolCall } from '../ToolCall';
import { useSparUIContext } from '../../../../../api/context';
import { useToggle } from '../../../../../hooks/useToggle';
import { useThreadSearchStore } from '../../../../../state/useThreadSearchStore';
import { useFeatureFlag } from '../../../../../hooks/useFeatureFlag';
import { SparUIFeatureFlag } from '../../../../../api';
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

type ThreadContentItem = ThreadMessage['content'][number];

const TOOL_CALLS_TO_IGNORE: Record<string, boolean> = {
  quick_reply: true,
  consider_runbook_adherence: true,
  ready_to_reply_to_user: true,
  unable_to_satisfy_request: true,
};
export const shouldIgnoreToolCall = (toolCallName: string) => TOOL_CALLS_TO_IGNORE[toolCallName] === true;

const isKind = <K extends string>(
  content: ThreadContentItem,
  kind: K,
): content is Extract<ThreadContentItem, { kind: K }> => {
  return typeof content === 'object' && content !== null && 'kind' in content && content.kind === kind;
};

const isVegaChartContent = (content: ThreadContentItem): content is ThreadVegaChartContent =>
  isKind(content, 'vega_chart');

const isQuickActionsContent = (content: ThreadContentItem): content is ThreadQuickActionsContent =>
  isKind(content, 'quick_actions');

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

  const messageContents = (message.content || []) as ThreadMessage['content'];

  const chartWidgetsFromContent: InlineWidget[] = messageContents.filter(isVegaChartContent).map((chartContent) => {
    // eslint-disable-next-line no-underscore-dangle
    const inlineSpec = chartContent._chart_spec;
    const hydratedSpec = (chartContent as { chart_spec?: unknown }).chart_spec ?? inlineSpec ?? undefined;
    return {
      id: chartContent.widget_id || chartContent.content_id,
      kind: 'chart',
      description: chartContent.description,
      status: chartContent.status ?? 'done',
      error: chartContent.error,
      thinking: chartContent.thinking,
      result: {
        spec: hydratedSpec,
        chart_spec_raw: chartContent.chart_spec_raw,
        sub_type: chartContent.sub_type,
      },
    };
  });

  const buttonWidgetsFromContent: InlineWidget[] = messageContents
    .filter(isQuickActionsContent)
    .map((buttonContent) => ({
      id: buttonContent.widget_id || buttonContent.content_id,
      kind: 'buttons',
      description: buttonContent.description,
      status: buttonContent.status ?? 'done',
      error: buttonContent.error,
      thinking: buttonContent.thinking,
      actions: buttonContent.actions || [],
    }));

  const inlineWidgets: InlineWidget[] = [...chartWidgetsFromContent, ...buttonWidgetsFromContent];

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
            parserRules={createMarkdownRules(inlineWidgets, message.message_id)}
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
    case 'vega_chart':
      return null;
    case 'quick_actions':
      // Inline buttons placeholder handles render
      return null;
    case 'attachment':
      return <Attachment key={content.content_id ?? content.name} content={content} />;
    default:
      return null;
  }
};

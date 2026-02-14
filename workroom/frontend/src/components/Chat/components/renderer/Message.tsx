import { FC, memo, useMemo } from 'react';
import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Banner } from '@sema4ai/components';
import { IconAlert } from '@sema4ai/icons';

import { MessageContentItemRenderer, shouldIgnoreToolCall } from './Item';
import { ToolCallGroup } from '../ToolCall';
import { AgentErrorStreamPayload } from '../../../../lib/AgentServerTypes';
import { PlanViewer } from './planning/PlanViewer';

type Props = {
  message: ThreadMessage | AgentErrorStreamPayload;
  streaming: boolean;
  isLastMessage?: boolean;
  isFirstMessage?: boolean;
};

type ThreadMessageContent = ThreadMessage['content'];
export const getGroupedMessageContent = (messageContent: ThreadMessageContent, messageComplete: boolean) => {
  /**
   * If message stream started with empty content show thinking state as placeholder
   */
  if (messageContent.length === 0 && !messageComplete) {
    // Wrap in nested array so ToolCallGroup renders (shows pulsing indicator immediately)
    // Use stable placeholder ID to prevent component remounting on re-renders
    return [
      [
        {
          kind: 'thought' as const,
          thought: '',
          complete: false,
          content_id: 'placeholder-thought',
        },
      ],
    ];
  }

  return messageContent
    .reduce<(ThreadMessageContent | ThreadMessageContent[number])[]>((acc, content) => {
      /**
       * Skip internal tool calls that don't bring value to the user
       */
      if (content.kind === 'tool_call' && shouldIgnoreToolCall(content.name)) {
        return acc;
      }

      if (['thought', 'tool_call'].includes(content.kind)) {
        const previousContent = acc[acc.length - 1];
        if (Array.isArray(previousContent)) {
          const lastGroupedContentItem = previousContent[previousContent.length - 1];

          // Replace consecutive empty thoughts with latest empty thought only
          if (
            content.kind === 'thought' &&
            content.thought === '' &&
            lastGroupedContentItem?.kind === 'thought' &&
            lastGroupedContentItem.thought === ''
          ) {
            previousContent[previousContent.length - 1] = content;
            return acc;
          }

          previousContent.push(content);
          return acc;
        }

        acc.push([content]);
        return acc;
      }

      acc.push(content);
      return acc;
    }, [])
    .map((content) => {
      // Keep single thought/tool_call items as arrays so ToolCallGroup renders (shows pulsing indicator)
      if (Array.isArray(content) && content.length === 1) {
        const item = content[0];
        if (item.kind === 'thought' || item.kind === 'tool_call') {
          return content;
        }
        return item;
      }
      return content;
    });
};

const Renderer: FC<{
  message: ThreadMessage;
  streaming: boolean;
  isLastMessage?: boolean;
  isFirstMessage?: boolean;
}> = ({ message, streaming, isLastMessage, isFirstMessage }) => {
  const groupedMessageContent = useMemo(() => {
    const messageContent = message.content ?? [];
    return getGroupedMessageContent(messageContent, message.complete);
  }, [message.content, message.complete]);

  const messagePlatform = message.agent_metadata?.platform;
  const platform = typeof messagePlatform === 'string' ? messagePlatform : undefined;

  // Use stable key prefix for streaming messages to prevent remounts during streaming
  const keyPrefix = message.complete ? message.message_id : 'streaming';

  // Keys use stable prefix + index to prevent component remounting during streaming
  // eslint-disable-next-line react/no-array-index-key
  const renderedMessageContent = groupedMessageContent.map((processedContent, groupIndex) => {
    if (Array.isArray(processedContent)) {
      return (
        <ToolCallGroup
          // eslint-disable-next-line react/no-array-index-key
          key={`group-${keyPrefix}-${groupIndex}`}
          messageContent={processedContent}
          messageComplete={message.complete}
          platform={platform}
        >
          {processedContent.map((processedContentItem, itemIndex) => (
            <MessageContentItemRenderer
              // eslint-disable-next-line react/no-array-index-key
              key={`group-item-${keyPrefix}-${groupIndex}-${itemIndex}`}
              message={message}
              messageContentItem={processedContentItem}
              streaming={streaming}
              platform={platform}
              isLastMessage={isLastMessage}
              isFirstMessage={isFirstMessage}
              isLastContentItem={
                groupedMessageContent.length - 1 === groupIndex && processedContent.length - 1 === itemIndex
              }
            />
          ))}
        </ToolCallGroup>
      );
    }
    return (
      <MessageContentItemRenderer
        // eslint-disable-next-line react/no-array-index-key
        key={`item-${keyPrefix}-${groupIndex}`}
        message={message}
        messageContentItem={processedContent}
        streaming={streaming}
        platform={platform}
        isLastMessage={isLastMessage}
        isFirstMessage={isFirstMessage}
        isLastContentItem={groupedMessageContent.length - 1 === groupIndex}
      />
    );
  });

  // TODO: rename metadata consistency key to 'plan'?
  if (message.role === 'agent' && message.agent_metadata?.consistency) {
    renderedMessageContent.push(
      <PlanViewer key={`plan-${message.message_id}`} metadata={message.agent_metadata?.consistency} />,
    );
  }

  return renderedMessageContent;
};

const MessageRendererComponent: FC<Props> = ({ message, streaming, isLastMessage, isFirstMessage }) => {
  // TODO-V2: Styling of a stream error
  if ('error_id' in message) {
    return <Banner message="An error occurred" description={message.message} icon={IconAlert} variant="error" />;
  }

  return (
    <Renderer message={message} streaming={streaming} isLastMessage={isLastMessage} isFirstMessage={isFirstMessage} />
  );
};

export const MessageRenderer = memo(MessageRendererComponent);

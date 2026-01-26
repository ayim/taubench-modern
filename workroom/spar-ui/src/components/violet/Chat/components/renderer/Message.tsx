import { FC, memo, useMemo } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Banner } from '@sema4ai/components';
import { IconAlert } from '@sema4ai/icons';

import { MessageContentItemRenderer, shouldIgnoreToolCall } from './Item';
import { ToolCallGroup } from '../ToolCall';
import { AgentErrorStreamPayload } from '../../../../../lib/AgentServerTypes';
import { DocCards } from './DocCards';

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
    return [
      {
        kind: 'thought' as const,
        thought: '',
        complete: false,
        content_id: uuidv4(),
      },
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
    .map((content) => (Array.isArray(content) && content.length === 1 ? content[0] : content));
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

  const rawMessageContent = message.content ?? [];

  const renderedMessageContent = groupedMessageContent.map((processedContent, groupIndex) => {
    if (Array.isArray(processedContent)) {
      return (
        <ToolCallGroup
          key={`group-${processedContent[0].content_id}`}
          messageContent={processedContent}
          messageComplete={message.complete}
          platform={platform}
          rawMessageContent={rawMessageContent}
        >
          {processedContent.map((processedContentItem, itemIndex) => (
            <MessageContentItemRenderer
              key={`group-item-${processedContentItem.content_id}`}
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
        key={`group-item-${processedContent.content_id}`}
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

  const docCards = useMemo(() => {
    const maybeCards = message.agent_metadata?.doc_cards;
    return Array.isArray(maybeCards) ? maybeCards : [];
  }, [message.agent_metadata?.doc_cards]);

  if (message.role === 'agent' && docCards.length > 0) {
    renderedMessageContent.push(
      <DocCards key={`doc-cards-${message.message_id}`} cards={docCards} messageId={message.message_id} />,
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

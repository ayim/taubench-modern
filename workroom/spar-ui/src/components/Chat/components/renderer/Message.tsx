import { FC, useMemo } from 'react';
import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Banner } from '@sema4ai/components';
import { IconAlert } from '@sema4ai/icons';

import { MessageContentItemRenderer, shouldIgnoreToolCall } from './Item';
import { ToolCallGroup } from '../ToolCall';
import { AgentErrorStreamPayload } from '../../../../lib/AgentServerTypes';

type Props = {
  message: ThreadMessage | AgentErrorStreamPayload;
  streaming: boolean;
};

type ThreadMessageContent = ThreadMessage['content'];
const getGroupedMessageContent = (messageContent: ThreadMessageContent) =>
  messageContent
    .reduce<(ThreadMessageContent | ThreadMessageContent[number])[]>((acc, content) => {
      if (content.kind === 'tool_call' && shouldIgnoreToolCall(content.name)) {
        return acc;
      }

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
    }, [])
    .map((content) => (Array.isArray(content) && content.length === 1 ? content[0] : content));

const Renderer: FC<{ message: ThreadMessage; streaming: boolean }> = ({ message, streaming }) => {
  const groupedMessageContent = useMemo(() => {
    const messageContent = message.content ?? [];
    return getGroupedMessageContent(messageContent);
  }, [message.content]);

  return groupedMessageContent.map((processedContent) => {
    if (Array.isArray(processedContent)) {
      return (
        <ToolCallGroup
          key={`group-${processedContent[0].content_id}`}
          messageContent={processedContent}
          messageComplete={message.complete}
        >
          {processedContent.map((processedContentItem) => (
            <MessageContentItemRenderer
              key={`group-item-${processedContentItem.content_id}`}
              message={message}
              messageContentItem={processedContentItem}
              streaming={streaming}
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
      />
    );
  });
};

export const MessageRenderer: FC<Props> = ({ message, streaming }) => {
  // TODO-V2: Styling of a stream error
  if ('error_id' in message) {
    return <Banner message="An error occurred" description={message.message} icon={IconAlert} variant="error" />;
  }

  return <Renderer message={message} streaming={streaming} />;
};

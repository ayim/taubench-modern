import { FC, useEffect, useRef } from 'react';
import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Banner, Box, Button, Chat, useClipboard } from '@sema4ai/components';
import { IconAlert, IconCheck2, IconCopy, IconThumbsDown } from '@sema4ai/icons';
import MarkJS from 'mark.js';

import { markdownRules } from './markdown';
import { Attachment } from './Attachment';
import { ToolCall } from './ToolCall';
import { AgentErrorStreamPayload } from '../../../lib/AgentServerTypes';
import { useThreadSearchStore } from '../../../state/useThreadSearchStore';
import { useToggle } from '../../../hooks/useToggle';
import { FeedbackDialog } from './FeedbackDialog';
import { useSparUIContext } from '../../../api/context';

type Props = {
  message: ThreadMessage | AgentErrorStreamPayload;
  streaming: boolean;
};

export const MessageRenderer: FC<Props> = ({ message, streaming }) => {
  const { query } = useThreadSearchStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();
  const { val: isFeedbackDialogOpen, setTrue: openFeedbackDialog, setFalse: closeFeedbackDialog } = useToggle();
  const { sparAPIClient } = useSparUIContext();

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
          <>
            <Chat.Markdown
              ref={containerRef}
              messageId={message.message_id}
              streaming={streaming}
              parserRules={markdownRules}
              key={content.content_id}
            >
              {content.text}
            </Chat.Markdown>
            <Box display="flex" justifyContent="flex-end" gap="$4">
              <Button
                icon={copiedToClipboard ? IconCheck2 : IconCopy}
                onClick={onCopyToClipboard(content.text)}
                aria-label="Copy to clipboard"
                variant="ghost-subtle"
                size="small"
              />
              {sparAPIClient.sendFeedback && (
                <Button
                  icon={IconThumbsDown}
                  onClick={() => openFeedbackDialog()}
                  aria-label="Feedback"
                  variant="ghost-subtle"
                  size="small"
                />
              )}
            </Box>
            {isFeedbackDialogOpen && sparAPIClient.sendFeedback && (
              <FeedbackDialog
                open={isFeedbackDialogOpen}
                onClose={closeFeedbackDialog}
              />
            )}
          </>
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

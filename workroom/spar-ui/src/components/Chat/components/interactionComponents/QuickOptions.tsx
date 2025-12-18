import { Box, Button, Tooltip } from '@sema4ai/components';
import { IconEnterKey } from '@sema4ai/icons';
import { FC } from 'react';

import { useMessageStream, useParams } from '../../../../hooks';
import { useThreadMessagesQuery } from '../../../../queries/threads';
import { InteractionComponent } from './shared';

type QuickOption = {
  message: string;
  title: string;
  iconName?: string;
  primary?: boolean;
};

export type QuickOptionsPayload = {
  type: 'quick-options';
  data: QuickOption[];
};

type OptionProps = {
  choice: QuickOption;
  onSelect: (message: { text: string }, files: File[]) => void;
  disabled: boolean;
  isRunning: boolean;
};

const QuickOptionButton: FC<OptionProps> = ({ choice, onSelect, disabled, isRunning }) => {
  return (
    <Tooltip text={!disabled ? choice.message : undefined}>
      <Button
        round
        loading={isRunning}
        variant="outline"
        disabled={disabled}
        onClick={() => onSelect({ text: choice.message }, [])}
        icon={IconEnterKey}
        truncate
      >
        {choice.title}
      </Button>
    </Tooltip>
  );
};

export const QuickOptions: InteractionComponent<QuickOptionsPayload> = ({ payload: { data: choices }, messageId }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');

  /**
   * Use only cached messages without fetching
   * - stream might still be in flight and this will overwrite stream content as messages might not be persisted yet
   */
  const { data: messages } = useThreadMessagesQuery({ threadId }, { enabled: false });

  const { streamingMessages, sendMessage } = useMessageStream({
    agentId,
    threadId,
  });

  if (!messages) return null;

  const lastHumanMessageIndex = messages.findLastIndex((m) => m.role === 'user');
  const ourMessageIndex = messages.findLastIndex((m) => m.message_id === messageId);
  const moreRecentHumanMessage = lastHumanMessageIndex > ourMessageIndex;

  const streaming = !!streamingMessages;
  const running = streaming && lastHumanMessageIndex === ourMessageIndex + 1;

  const wasSelected = (choice: QuickOption) => {
    const messageAfterThisOne = messages[ourMessageIndex + 1];
    return !!messageAfterThisOne?.content?.some((c) => c.kind === 'text' && c.text === choice.message);
  };

  return (
    <Box display="flex" gap="$8" flexWrap="wrap" marginTop="$16">
      {choices
        .filter(() => {
          // Hide disabled buttons for previous messages
          const isDisabled = streaming || moreRecentHumanMessage;
          return !isDisabled;
        })
        .map((choice) => (
          <QuickOptionButton
            key={choice.title}
            choice={choice}
            isRunning={wasSelected(choice) && running}
            onSelect={sendMessage}
            disabled={false}
          />
        ))}
    </Box>
  );
};

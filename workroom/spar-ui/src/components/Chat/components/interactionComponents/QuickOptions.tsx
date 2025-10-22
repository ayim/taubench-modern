import { Box, Button, Tooltip } from '@sema4ai/components';
import * as Icons from '@sema4ai/icons';
import { FC, useMemo } from 'react';

import { useMessageStream, useParams } from '../../../../hooks';
import { useThreadMessagesQuery } from '../../../../queries/threads';
import { InteractionComponent } from './shared';

type IconsType = typeof Icons;

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
  onSelect: (message: string, files: File[]) => void;
  disabled: boolean;
  isRunning: boolean;
};

const QuickOptionButton: FC<OptionProps> = ({ choice, onSelect, disabled, isRunning }) => {
  const IconComponent = useMemo(() => {
    if (choice.iconName !== undefined && Object.keys(Icons).includes(choice.iconName))
      return Icons[choice.iconName as keyof IconsType];

    return Icons.IconReply;
  }, [choice.iconName]);

  return (
    <Tooltip text={!disabled ? choice.message : undefined}>
      <Button
        round
        loading={isRunning}
        variant={choice.primary ? 'primary' : 'outline'}
        disabled={disabled}
        onClick={() => onSelect(choice.message, [])}
        icon={IconComponent}
        truncate
      >
        {choice.title}
      </Button>
    </Tooltip>
  );
};

export const QuickOptions: InteractionComponent<QuickOptionsPayload> = ({ payload: { data: choices }, messageId }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { data: messages } = useThreadMessagesQuery({
    threadId,
  });

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
    <Box display="flex" gap="$8" flexWrap="wrap">
      {choices.map((choice) => (
        <QuickOptionButton
          key={choice.title}
          choice={choice}
          isRunning={wasSelected(choice) && running}
          onSelect={sendMessage}
          disabled={streaming || moreRecentHumanMessage}
        />
      ))}
    </Box>
  );
};

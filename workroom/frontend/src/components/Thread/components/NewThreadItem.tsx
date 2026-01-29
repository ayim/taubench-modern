import { FC } from 'react';
import { IconWriteNote } from '@sema4ai/icons';
import { List } from '@sema4ai/components';
import { useFeatureFlag, FeatureFlag } from '../../../hooks';
import { useCreateThread } from '../../../hooks/useCreateThread';
import { ThreadListItemContainer } from './ThreadsList/styles';

export const NewThreadItem: FC = () => {
  const { onNewThread, isCreatingThread } = useCreateThread();
  const { enabled: isChatInteractive } = useFeatureFlag(FeatureFlag.agentChatInput);

  const isNewThreadDisabled = isCreatingThread || !isChatInteractive;
  return (
    <ThreadListItemContainer>
      <List.Item icon={IconWriteNote} disabled={isNewThreadDisabled} onClick={onNewThread}>
        New Conversation
      </List.Item>
    </ThreadListItemContainer>
  );
};

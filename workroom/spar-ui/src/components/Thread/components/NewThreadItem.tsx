import { FC } from 'react';
import { IconWriteNote } from '@sema4ai/icons';
import { List } from '@sema4ai/components';
import { useFeatureFlag } from '../../../hooks';
import { useCreateThread } from '../../../hooks/useCreateThread';
import { SparUIFeatureFlag } from '../../../api';
import { ThreadListItemContainer } from './ThreadsList/styles';

export const NewThreadItem: FC = () => {
  const { onNewThread, isCreatingThread } = useCreateThread();
  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const isNewThreadDisabled = isCreatingThread || !isChatInteractive;
  return (
    <ThreadListItemContainer>
      <List.Item icon={IconWriteNote} disabled={isNewThreadDisabled} onClick={onNewThread}>
        New Chat
      </List.Item>
    </ThreadListItemContainer>
  );
};

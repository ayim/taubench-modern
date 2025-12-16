import { IconPlusSmall } from '@sema4ai/icons';
import { List } from '@sema4ai/components';
import { useLinkProps } from '../../../common/link';
import { useFeatureFlag, useParams } from '../../../hooks';
import { SparUIFeatureFlag } from '../../../api';
import { ThreadListItemContainer, ThreadListLinkContainer } from '../../Thread/components/ThreadsList/styles';

export const NewWorkItem = () => {
  const { agentId } = useParams('/workItem/$agentId');
  const linkProps = useLinkProps('/workItem/$agentId/create', { agentId });

  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  if (!isChatInteractive) {
    return (
      <ThreadListItemContainer>
        <List.Item icon={IconPlusSmall} disabled>
          New Work Item
        </List.Item>
      </ThreadListItemContainer>
    );
  }

  return (
    <ThreadListLinkContainer>
      <List.Link icon={IconPlusSmall} {...linkProps}>
        New Work Item
      </List.Link>
    </ThreadListLinkContainer>
  );
};

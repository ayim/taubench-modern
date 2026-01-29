import { IconPlusSmall } from '@sema4ai/icons';
import { List } from '@sema4ai/components';
import { useParams } from '@tanstack/react-router';

import { ListItemLink } from '~/components/link';
import { useFeatureFlag, FeatureFlag } from '../../../hooks';
import { ThreadListItemContainer, ThreadListLinkContainer } from '../../Thread/components/ThreadsList/styles';

export const NewWorkItem = () => {
  const { agentId, tenantId } = useParams({ strict: false });

  const { enabled: isChatInteractive } = useFeatureFlag(FeatureFlag.agentChatInput);

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
      <ListItemLink icon={IconPlusSmall} to="/tenants/$tenantId/worker/$agentId/create" params={{ tenantId, agentId }}>
        New Work Item
      </ListItemLink>
    </ThreadListLinkContainer>
  );
};

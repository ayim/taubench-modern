import { FC } from 'react';

import { useAgentQuery } from '../../queries/agents';
import { useParams, useQueryDataGuard } from '../../hooks';
import { ThreadsList } from './components/ThreadsList';
import { Chat } from '../Chat';

export const Thread: FC = () => {
  const { agentId, threadId } = useParams('/conversational/$agentId/$threadId');

  const { ...agentQueryState } = useAgentQuery({ agentId });

  const queryDataGuard = useQueryDataGuard([agentQueryState]);

  if (queryDataGuard) {
    return queryDataGuard;
  }

  return (
    <>
      <ThreadsList />
      <Chat agentId={agentId} threadId={threadId} />
    </>
  );
};

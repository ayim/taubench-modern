import { FC } from 'react';

import { useAgentQuery } from '../../queries/agents';
import { useParams, useQueryDataGuard } from '../../hooks';
import { ThreadsList } from './components/ThreadsList';
import { Chat } from '../Chat';
import { WorkerList } from './components/WorkerList';

export const Thread: FC = () => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');

  const { data: agent, ...agentQueryState } = useAgentQuery({ agentId });

  const queryDataGuard = useQueryDataGuard([agentQueryState]);

  if (queryDataGuard) {
    return queryDataGuard;
  }

  const Sidebar = agent?.metadata?.mode === 'worker' ? WorkerList : ThreadsList;

  return (
    <>
      <Sidebar />
      <Chat agentId={agentId} threadId={threadId} />
    </>
  );
};

import { FC } from 'react';

import { useAgentQuery } from '../../queries/agents';
import { useThreadQuery } from '../../queries/threads';
import { useParams, useQueryDataGuard } from '../../hooks';
import { ThreadsList } from './components/ThreadsList/ThreadsList';
import { Chat } from '../Chat';

export const Thread: FC = () => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');

  const { ...agentQueryState } = useAgentQuery({ agentId });
  const { data: thread } = useThreadQuery({ threadId });

  const queryDataGuard = useQueryDataGuard([agentQueryState]);
  if (queryDataGuard) {
    return queryDataGuard;
  }

  // Check if this is an evaluation thread (has scenario_id in metadata)
  const isEvaluationThread = Boolean(thread?.metadata?.scenario_id);

  return (
    <>
      {/* Hide threads list for evaluation threads - navigation only through eval sidebar */}
      {!isEvaluationThread && <ThreadsList />}
      <Chat agentId={agentId} threadId={threadId} agentType="conversational" thread={thread} />
    </>
  );
};

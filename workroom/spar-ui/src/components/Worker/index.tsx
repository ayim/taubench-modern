import { styled } from '@sema4ai/theme';
import { FC } from 'react';

import { useParams, useQueryDataGuard } from '../../hooks';
import { useAgentQuery } from '../../queries/agents';
import { Chat } from '../Chat';
import { WorkerList } from './components/WorkerList';

const SubView = styled.section`
  height: 100%;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
`;

export const Worker: FC = () => {
  const { agentId, workItemId, threadId } = useParams('/workItem/$agentId/$workItemId/$threadId');

  const { ...agentQueryState } = useAgentQuery({ agentId });

  const queryDataGuard = useQueryDataGuard([agentQueryState]);

  if (queryDataGuard) {
    return queryDataGuard;
  }

  return (
    <>
      <WorkerList />

      {!workItemId && <SubView>Select or create a work item</SubView>}
      {workItemId && !threadId && <SubView>Work item doesn&apos;t have a thread yet. Please wait a moment.</SubView>}
      {workItemId && threadId && <Chat agentId={agentId} threadId={threadId} agentType="workItem" />}
    </>
  );
};

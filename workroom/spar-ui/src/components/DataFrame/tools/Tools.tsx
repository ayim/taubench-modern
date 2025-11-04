import { FC, useEffect, useState } from 'react';
import { useParams, useStateTransitionCallback } from '../../../hooks';
import { useDataFramesQuery } from '../../../queries/dataFrames';

const DATA_FRAME_REFETCH_GRACE_PERIOD = 1000;

const DataFrameCallback: FC<{ onComplete: () => void }> = ({ onComplete }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { refetch } = useDataFramesQuery({ threadId }, { enabled: false });

  useEffect(() => {
    setTimeout(() => {
      refetch().finally(() => {
        onComplete();
      });
    }, DATA_FRAME_REFETCH_GRACE_PERIOD);
  }, [refetch, agentId, threadId]);

  return null;
};

export type DataFrameCallbackState = 'in_progress' | 'done' | 'failed';
export const DataFrameCallbackDataFrameCreation: FC<{
  state: DataFrameCallbackState;
}> = ({ state }) => {
  const [triggered, setTriggered] = useState(false);
  const onTransitionTriggered = () => setTriggered(true);
  const onTransitionComplete = () => setTriggered(false);

  useStateTransitionCallback<DataFrameCallbackState>(
    { onTransition: onTransitionTriggered, from: 'in_progress', to: 'done' },
    state,
  );
  if (triggered) return <DataFrameCallback onComplete={onTransitionComplete} />;
  return null;
};

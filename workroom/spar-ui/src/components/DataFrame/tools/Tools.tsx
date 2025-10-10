import { FC, useEffect, useState } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { useParams } from '../../../hooks';
import { useDataFramesQuery } from '../../../queries/dataFrames';

const DATA_FRAME_REFETCH_GRACE_PERIOD = 500;

const DataFrameCallback: FC<{ onComplete: () => void }> = ({ onComplete }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { refetch } = useDataFramesQuery({ threadId });

  useEffect(() => {
    setTimeout(() => {
      refetch().finally(() => {
        onComplete();
      });
    }, DATA_FRAME_REFETCH_GRACE_PERIOD);
  }, [refetch, agentId, threadId]);

  return null;
};

export const DataFrameCallbackDataFrameCreation: FC<{ tool: ThreadToolUsageContent }> = ({ tool }) => {
  const [triggered, setTriggered] = useState(false);
  const onComplete = () => setTriggered(false);

  const isRunning = ['streaming', 'pending', 'running'].includes(tool.status);
  useEffect(() => {
    if (isRunning) {
      setTriggered(true);
    }
  }, [isRunning]);

  if (triggered && tool.complete && tool.status !== 'failed') return <DataFrameCallback onComplete={onComplete} />;
  return null;
};

import { FC, useEffect } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { useParams } from '../../../hooks';
import { useDataFramesQuery } from '../../../queries/dataFrames';

const DATA_FRAME_REFETCH_GRACE_PERIOD = 500;

export const DataFrameCallbackDataFrameCreation: FC<{ tool: ThreadToolUsageContent }> = ({ tool }) => {
  const { threadId } = useParams('/thread/$agentId/$threadId');
  const { refetch } = useDataFramesQuery({ threadId });

  const isComplete = tool.complete;
  useEffect(() => {
    if (isComplete) {
      setTimeout(() => {
        refetch();
      }, DATA_FRAME_REFETCH_GRACE_PERIOD);
    }
  }, [isComplete, refetch]);

  return null;
};

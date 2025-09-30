import { FC, useEffect, useMemo, useState } from 'react';
import { Box, Button, DataFrame, Menu, Typography } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconMenu, IconTableRows } from '@sema4ai/icons';

import { useMessageStream } from '../../hooks';
import { ListDataFrames, useDataFrameSliceInfiniteQuery, useDataFramesQuery } from '../../queries/dataFrames';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  width: 100%;
  position: relative;
  min-height: 200px;

  > div {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
  }
`;

const StyledDataFrame = styled(DataFrame)`
  > div {
    padding: 0 ${({ theme }) => theme.space.$4};
  }
`;

type DataFrame = {
  column_headers: string[];
  thread_id: string;
  data_frame_id: string;
  num_rows: number;
  name: string;
  description?: string | null;
  parent_data_frame_ids: string[] | null;
};

const getDataFrameColumns = (dataFrame: DataFrame) => {
  return dataFrame.column_headers.map((header: string) => {
    return {
      id: header,
      title: header,
    };
  });
};

interface DataFrameEntryProps {
  dataFrame: DataFrame;
  agentId: string;
}

const DataFrameEntry: FC<DataFrameEntryProps> = ({ dataFrame, agentId }) => {
  const { sendMessage } = useMessageStream({
    agentId,
    threadId: dataFrame.thread_id,
  });

  const [resize, onResize] = useState({});
  const columns = useMemo(() => getDataFrameColumns(dataFrame), [dataFrame]);

  const {
    data = [],
    fetchNextPage,
    hasNextPage,
    isFetching,
    isLoading,
  } = useDataFrameSliceInfiniteQuery({
    threadId: dataFrame.thread_id,
    dataFrameId: dataFrame.data_frame_id,
    totalRows: dataFrame.num_rows,
  });

  const columnsWithActions = useMemo(() => {
    return columns.map((column) => {
      return {
        ...column,
        actions: [
          {
            label: 'Remove Column',
            onClick: () => sendMessage(`Remove column "${column.title}" from data frame "${dataFrame.name}".`, []),
          },
        ],
      };
    });
  }, [columns, dataFrame.name, sendMessage]);

  if (isLoading) return null;

  return (
    <StyledDataFrame
      columns={columnsWithActions}
      data={data}
      resize={resize}
      onResize={onResize}
      onLoadNext={fetchNextPage}
      hasNext={hasNextPage}
      loading={isFetching}
      total={dataFrame.num_rows}
    />
  );
};

interface DataFrameViewComponentProps {
  agentId: string;
  dataFrames: DataFrame[];
  activeDataFrame: DataFrame;
  activeDataFrameIndex: number;
  setActiveDataFrameIndex: (index: number) => void;
}

const DataFrameViewComponent: FC<DataFrameViewComponentProps> = ({
  agentId,
  dataFrames,
  activeDataFrame,
  activeDataFrameIndex,
  setActiveDataFrameIndex,
}) => {
  const dataFrameCount = dataFrames.length;

  useEffect(() => {
    setActiveDataFrameIndex(dataFrameCount - 1);
  }, [dataFrameCount, setActiveDataFrameIndex]);

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <div>
        <Box display="flex" flexDirection="column" gap="$8" pb="$4" px="$4">
          <Box display="flex" gap="$12">
            <Box display="flex" alignItems="center" gap="$8">
              <IconTableRows />
              <Typography variant="display-small" style={{ wordBreak: 'break-all' }}>
                {activeDataFrame.name}
              </Typography>
            </Box>

            <Box flex={1} />

            {dataFrames.length > 1 && (
              <Box display="flex" alignItems="center" gap="$12">
                <Menu trigger={<Button icon={IconMenu} variant="outline" aria-label="choose data frame" round />}>
                  {dataFrames.map((frame, index) => (
                    <Menu.Item
                      key={frame.name ?? index}
                      onClick={() => setActiveDataFrameIndex(index)}
                      aria-selected={index === activeDataFrameIndex}
                      description={frame.description}
                    >
                      {frame.name}
                    </Menu.Item>
                  ))}
                </Menu>
              </Box>
            )}
          </Box>

          {activeDataFrame.description && (
            <Typography variant="body-medium">{activeDataFrame.description}</Typography>
          )}
        </Box>

        {activeDataFrame !== undefined && (
          <Container>
            <DataFrameEntry key={activeDataFrameIndex} dataFrame={activeDataFrame} agentId={agentId} />
          </Container>
        )}
      </div>
    </Box>
  );
};

const EmptyDataFrameView: FC = () => {
  return (
    <Box display="flex" flexDirection="column" height="100%">
      <Box display="flex" flexDirection="column" flex={1} alignItems="center" justifyContent="center" gap="$8">
        <IconTableRows size={100} />
        <Typography variant="body-medium" color="content.subtle.light">
          No Data Frames created.
        </Typography>
      </Box>
    </Box>
  );
};

export const DataFrameView: FC<{ threadId: string; agentId: string; initialData?: ListDataFrames }> = ({
  threadId,
  agentId,
  initialData,
}) => {
  const [activeDataFrameIndex, setActiveDataFrameIndex] = useState<number>(0);
  const { data: allDataFrames = [] } = useDataFramesQuery({ threadId, queryOptions: { initialData } });

  const dataFrame = allDataFrames[activeDataFrameIndex];

  if (!dataFrame) return <EmptyDataFrameView />;

  return (
    <DataFrameViewComponent
      agentId={agentId}
      dataFrames={allDataFrames}
      activeDataFrame={dataFrame}
      activeDataFrameIndex={activeDataFrameIndex}
      setActiveDataFrameIndex={setActiveDataFrameIndex}
    />
  );
};

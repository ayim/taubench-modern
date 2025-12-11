import { Box, Button, DataFrame, ListSkeleton, SkeletonLoader, Typography } from '@sema4ai/components';
import { FC, useMemo, useState } from 'react';

import { useParams } from '../../../../../hooks';
import { useDataFrameSliceInfiniteQuery, useDataFramesQuery } from '../../../../../queries/dataFrames';

interface InlineDataFrameMountProps {
  name?: string;
  columns?: string[];
  rows?: number;
}

export const InlineDataFrameMount: FC<InlineDataFrameMountProps> = ({ name, columns, rows }) => {
  const { threadId } = useParams('/thread/$agentId/$threadId');
  const pageSize = rows && rows > 0 ? rows : 10;
  const [expanded, setExpanded] = useState(true);

  const {
    data: frames,
    isLoading: framesLoading,
    isError: framesError,
  } = useDataFramesQuery({ threadId }, { enabled: Boolean(name) });

  const frame = useMemo(() => frames?.find((f) => f.name === name), [frames, name]);

  const selectedColumns = useMemo(() => {
    if (!frame) return [] as string[];
    if (!columns || columns.length === 0) return frame.column_headers;
    const filtered = columns.filter((c) => frame.column_headers.includes(c));
    return filtered.length > 0 ? filtered : frame.column_headers;
  }, [columns, frame]);

  const {
    data = [],
    fetchNextPage,
    hasNextPage,
    isFetching,
    isLoading,
  } = useDataFrameSliceInfiniteQuery({
    threadId,
    dataFrameId: frame?.data_frame_id ?? '',
    totalRows: frame?.num_rows ?? 0,
    options: {
      limit: pageSize,
      column_names: selectedColumns.length > 0 ? selectedColumns : undefined,
    },
    queryOptions: {
      enabled: Boolean(frame?.data_frame_id) && expanded,
    },
  });

  if (!name) {
    return (
      <Box padding="$3" borderRadius="$3" backgroundColor="background.subtle">
        <Typography variant="body-small" color="content.subtle">
          No dataframe name provided.
        </Typography>
      </Box>
    );
  }

  if (framesLoading || (isLoading && expanded)) {
    return (
      <Box
        padding="$3"
        borderRadius="$3"
        backgroundColor="background.subtle"
        style={{ border: '1px solid rgba(0,0,0,0.05)', maxWidth: '100%' }}
      >
        <SkeletonLoader skeleton={ListSkeleton} loading />
      </Box>
    );
  }

  if (framesError || !frame) {
    return (
      <Box padding="$3" borderRadius="$3" backgroundColor="background.subtle">
        <Typography variant="body-small" color="content.error">
          Dataframe &quot;{name}&quot; not found.
        </Typography>
      </Box>
    );
  }

  const columnsConfig = selectedColumns.map((col) => ({ id: col, title: col }));
  const totalRows = frame.num_rows;

  return (
    <Box padding="$4" borderRadius="$8" backgroundColor="background.subtle">
      <Box display="flex" alignItems="center" justifyContent="space-between" marginBottom="$2">
        <Box>
          <Typography variant="body-medium" color="content.primary">
            Table: {frame.name}
          </Typography>
          <Typography variant="body-small" color="content.subtle">
            {selectedColumns.length} cols · {totalRows} rows {rows ? `(showing ${pageSize} per page)` : ''}
          </Typography>
        </Box>
        <Button size="small" variant="ghost" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Hide' : 'Show'}
        </Button>
      </Box>

      {expanded ? (
        <DataFrame
          columns={columnsConfig}
          data={data}
          hasNext={hasNextPage}
          onLoadNext={fetchNextPage}
          loading={isFetching}
          total={totalRows}
          height="320px"
        />
      ) : null}
    </Box>
  );
};

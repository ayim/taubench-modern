import { useInfiniteQuery } from '@tanstack/react-query';
import { paths as AgentServerPaths } from '@sema4ai/agent-server-interface';
import { createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';
import { useSparUIContext } from '../api/context';

const getDataFramesQueryKey = ({ threadId }: { threadId: string }) => ['data-frames', threadId];
const getDataFramesSliceQueryKey = ({ threadId, dataFrameId }: { threadId: string; dataFrameId: string }) => [
  ...getDataFramesQueryKey({ threadId }),
  'slice',
  dataFrameId,
];
const getDataFrameQueryKey = ({ threadId, dataFrameName }: { threadId: string; dataFrameName: string }) => [
  ...getDataFramesQueryKey({ threadId }),
  dataFrameName,
];

export type ListDataFrames =
  AgentServerPaths['/api/v2/threads/{tid}/data-frames']['get']['responses'][200]['content']['application/json'];
export const dataFramesQueryOptions = createSparQueryOptions<{
  threadId: string;
  options?: { num_samples?: number };
  queryOptions?: { initialData?: ListDataFrames };
}>()(({ sparAPIClient, threadId, options, queryOptions }) => ({
  initialData: queryOptions?.initialData,
  queryKey: getDataFramesQueryKey({ threadId }),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/{tid}/data-frames', {
      params: { path: { tid: threadId }, query: { num_samples: options?.num_samples } },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch data frames', {
        code: response.code,
        resource: ResourceType.DataFrame,
      });
    }

    return response.data;
  },
}));

export const useDataFramesQuery = createSparQuery(dataFramesQueryOptions);

export const useDataFrameSliceInfiniteQuery = ({
  threadId,
  dataFrameId,
  options,
  totalRows,
  queryOptions,
}: {
  threadId: string;
  dataFrameId: string;
  options?: {
    limit?: number;
    column_names?: string[];
    data_frame_name?: string;
    order_by?: string;
    output_format?: 'json' | 'parquet';
  };
  totalRows: number;
  queryOptions?: {
    enabled?: boolean;
  };
}) => {
  const { sparAPIClient } = useSparUIContext();

  const result = useInfiniteQuery({
    queryKey: getDataFramesSliceQueryKey({ threadId, dataFrameId }),
    queryFn: async ({ pageParam }) => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/threads/{tid}/data-frames/slice', {
        params: {
          path: { tid: threadId },
        },
        body: {
          data_frame_id: dataFrameId,
          offset: typeof pageParam === 'number' ? pageParam : 0,
          limit: options?.limit,
          column_names: options?.column_names,
          data_frame_name: options?.data_frame_name,
          order_by: options?.order_by,
          output_format: options?.output_format ?? 'json',
        },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch data frame data', {
          code: response.code,
          resource: ResourceType.DataFrame,
        });
      }

      return response.data;
    },
    initialPageParam: 0,
    getNextPageParam: (_, pages) => {
      const nextPageOffset = pages.reduce<number>((acc, curr) => {
        const currentItem = (curr as unknown[]) ?? [];
        return acc + (currentItem.length ?? 0);
      }, 0);

      if (nextPageOffset >= totalRows) return null;
      return nextPageOffset;
    },
    select: (data) => data?.pages.flat() ?? [],
    ...queryOptions,
  });

  return result;
};

export type DataFrameQueryOptions =
  AgentServerPaths['/api/v2/threads/{tid}/data-frames/{data_frame_name}']['get']['parameters']['query'];
export const dataFrameQueryOptions = createSparQueryOptions<{
  threadId: string;
  dataFrameName: string;
  options?: DataFrameQueryOptions;
}>()(({ sparAPIClient, threadId, dataFrameName, options }) => ({
  queryKey: getDataFrameQueryKey({ threadId, dataFrameName }),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer(
      'get',
      '/api/v2/threads/{tid}/data-frames/{data_frame_name}',
      {
        params: {
          path: { tid: threadId, data_frame_name: dataFrameName },
          query: { output_format: 'json', ...options },
        },
      },
    );

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to get data frame file', {
        code: response.code,
        resource: ResourceType.DataFrame,
      });
    }

    return response.data;
  },
  /**
   * Expecting that data is immutable
   */
  staleTime: Infinity,
}));

export const useDataFrameQuery = createSparQuery(dataFrameQueryOptions);

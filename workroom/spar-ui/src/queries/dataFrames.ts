import { useInfiniteQuery } from '@tanstack/react-query';
import { paths as AgentServerPaths } from '@sema4ai/agent-server-interface';
import { createSparQuery, createSparQueryOptions } from './shared';
import { useSparUIContext } from '../api/context';

const getDataFramesQueryKey = ({ threadId }: { threadId: string }) => ['data-frames', threadId];
const getDataFramesInspectFileQueryKey = ({ threadId, fileId }: { threadId: string; fileId: string }) => [
  ...getDataFramesQueryKey({ threadId }),
  'inspect-file',
  fileId,
];
const getDataFramesSliceQueryKey = ({ threadId, dataFrameId }: { threadId: string; dataFrameId: string }) => [
  ...getDataFramesQueryKey({ threadId }),
  'slice',
  dataFrameId,
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
      throw new Error(response.message || 'Failed to fetch data frames');
    }

    return response.data;
  },
}));

export const useDataFramesQuery = createSparQuery(dataFramesQueryOptions);

export type DataFrameInspectFile =
  AgentServerPaths['/api/v2/threads/{tid}/inspect-file-as-data-frame']['get']['responses'][200]['content']['application/json'];
export const dataFramesInspectFileQueryOptions = createSparQueryOptions<{
  threadId: string;
  fileId: string;
  options?: { num_samples?: number; sheet_name?: string };
}>()(({ sparAPIClient, threadId, fileId, options }) => ({
  queryKey: getDataFramesInspectFileQueryKey({ threadId, fileId }),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/{tid}/inspect-file-as-data-frame', {
      params: {
        path: { tid: threadId },
        query: { file_id: fileId, num_samples: options?.num_samples, sheet_name: options?.sheet_name },
      },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to inspect data frame file');
    }

    return response.data;
  },
}));

export const useDataFramesInspectFileQuery = createSparQuery(dataFramesInspectFileQueryOptions);

export const useDataFrameSliceInfiniteQuery = ({
  threadId,
  dataFrameId,
  options,
  totalRows,
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
        throw new Error(response.message);
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
  });

  return result;
};

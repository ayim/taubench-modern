import { components } from '@sema4ai/agent-server-interface';
import { asyncForLoop } from '@sema4ai/robocloud-shared-utils';
import { InfiniteData, useInfiniteQuery } from '@tanstack/react-query';

import { createSparMutation, createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';
import { useSparUIContext } from '../api/context';

export type WorkItem = components['schemas']['WorkItem'];
export type WorkItemStatus = components['schemas']['WorkItemStatus'];
export type WorkItemsListResponse = components['schemas']['WorkItemsListResponse'];
type CreateWorkItemPayload = components['schemas']['CreateWorkItemPayload'];

/**
 * List Work items
 */
export type WorkItemsQueryParams = {
  agentId?: string;
  workItemStatus?: WorkItemStatus[];
  nameSearch?: string;
  limit?: number;
  offset?: number;
};

const DEFAULT_LIMIT = 100;
const DEFAULT_OFFSET = 0;

const normalizeWorkItemsParams = (params: WorkItemsQueryParams) => ({
  agentId: params.agentId,
  workItemStatus: params.workItemStatus,
  nameSearch: params.nameSearch,
  limit: params.limit ?? DEFAULT_LIMIT,
  offset: params.offset ?? DEFAULT_OFFSET,
});

export const workItemsQueryKey = (params: WorkItemsQueryParams) => {
  const normalized = normalizeWorkItemsParams(params);
  return [
    'work-items',
    normalized.agentId ?? 'all',
    normalized.workItemStatus?.join(',') ?? 'all-statuses',
    normalized.nameSearch ?? '',
    normalized.limit,
    normalized.offset,
  ];
};

export const workItemsQueryOptions = createSparQueryOptions<WorkItemsQueryParams>()<WorkItemsListResponse>(({
  sparAPIClient,
  agentId,
  workItemStatus,
  nameSearch,
  limit,
  offset,
}) => {
  const normalized = normalizeWorkItemsParams({ agentId, workItemStatus, nameSearch, limit, offset });

  return {
    queryKey: workItemsQueryKey({ agentId, workItemStatus, nameSearch, limit, offset }),
    queryFn: async (): Promise<WorkItemsListResponse> => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/work-items/', {
        params: {
          query: {
            agent_id: normalized.agentId,
            work_item_status: normalized.workItemStatus,
            name_search: normalized.nameSearch,
            limit: normalized.limit,
            offset: normalized.offset,
          },
        },
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to fetch work items');
      }

      return response.data;
    },
  };
});

export const useWorkItemsQuery = createSparQuery(workItemsQueryOptions);

const infiniteWorkItemsQueryKey = (params: { agentId: string; nameSearch: string | undefined }) => [
  'work-items-infinite',
  params.agentId,
  params.nameSearch ?? '',
];

const infiniteWorkItemsQueryKeyPrefix = (params: { agentId: string }) => ['work-items-infinite', params.agentId];

export const useWorkItemsInfiniteQuery = (params: {
  agentId: string;
  limit: number;
  nameSearch: string | undefined;
}) => {
  const { sparAPIClient } = useSparUIContext();

  return useInfiniteQuery<WorkItemsListResponse, QueryError>({
    queryKey: infiniteWorkItemsQueryKey(params),
    queryFn: async ({ pageParam }): Promise<WorkItemsListResponse> => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/work-items/', {
        params: {
          query: {
            agent_id: params.agentId,
            limit: params.limit,
            offset: typeof pageParam === 'number' ? pageParam : 0,
            name_search: params.nameSearch,
          },
        },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch work items', {
          code: response.code,
          resource: ResourceType.WorkItem,
        });
      }

      return response.data;
    },
    getNextPageParam: (lastPage, allPages) => {
      const currentOffset = allPages.length * params.limit;
      const hasMoreItems = (lastPage.records?.length ?? 0) === params.limit;
      return hasMoreItems ? currentOffset : undefined;
    },
    initialPageParam: 0,
  });
};

/**
 * Get Work Item
 */
export const workItemQueryKey = (workItemId: string) => ['work-item', workItemId];
export const workItemQueryOptions = createSparQueryOptions<{ workItemId: string }>()(
  ({ sparAPIClient, workItemId }) => ({
    queryKey: workItemQueryKey(workItemId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/work-items/{work_item_id}', {
        params: { path: { work_item_id: workItemId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch work item', {
          code: response.code,
          resource: ResourceType.WorkItem,
        });
      }

      return response.data;
    },
  }),
);

export const useWorkItemQuery = createSparQuery(workItemQueryOptions);

export const useCreateWorkItemMutation = createSparMutation<
  { agentId: string },
  {
    workItemName?: string;
    message: string;
    payload?: string;
    files?: File[];
  }
>()(({ agentId, sparAPIClient, queryClient }) => ({
  mutationFn: async ({ files, message, payload, workItemName }) => {
    const uploadFile = async (file: File, workItemId?: string) => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/work-items/upload-file', {
        params: { query: workItemId ? { work_item_id: workItemId } : {} },
        body: { file: file as unknown as string },
        bodySerializer(body: { file: string }) {
          const formData = new FormData();
          formData.append('file', body.file);
          return formData;
        },
      });

      if (!response.success) {
        throw new QueryError(response.message, { code: response.code, resource: ResourceType.WorkItem });
      }
      return response.data;
    };

    const createWorkItem = async (workItemId?: string) => {
      // request body to create work item
      const requestBody: CreateWorkItemPayload = {
        work_item_name: workItemName,
        agent_id: agentId,
        messages: [
          {
            role: 'user',
            content: [{ kind: 'text', text: message, complete: true }],
            complete: true,
            commited: true,
          },
        ],
      };

      if (payload && payload.trim()) {
        requestBody.payload = JSON.parse(payload);
      }

      if (workItemId) {
        requestBody.work_item_id = workItemId;
      }

      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/work-items/', {
        body: requestBody,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to create work item', {
          code: response.code,
          resource: ResourceType.WorkItem,
        });
      }

      return response.data;
    };

    const hasWorkItemFiles = files && files.length > 0;

    /** If no work item files, just create work item */
    if (!hasWorkItemFiles) {
      return createWorkItem();
    }

    /** Upload files and create work item using workItemId */
    const [firstFile, ...remainingFiles] = files;

    const firstFileResponse = await uploadFile(firstFile);

    const workItemId = firstFileResponse.work_item_id;
    if (!workItemId || typeof workItemId !== 'string') {
      throw new QueryError('Failed to get Work Item ID from first file upload', {
        code: 'bad_request',
        resource: ResourceType.WorkItem,
      });
    }

    await asyncForLoop(remainingFiles, async (file) => {
      await uploadFile(file, workItemId);
    });

    const createdWorkItem = await createWorkItem(workItemId);

    return createdWorkItem;
  },
  onSuccess: (createdWorkItem) => {
    queryClient.setQueriesData<InfiniteData<WorkItemsListResponse>>(
      {
        queryKey: infiniteWorkItemsQueryKeyPrefix({ agentId }),
        exact: false,
      },
      (oldData) => {
        if (!oldData || !createdWorkItem) {
          return oldData;
        }

        const updatedPages = [...oldData.pages];
        const firstPage = updatedPages[0];

        if (firstPage && firstPage.records) {
          updatedPages[0] = {
            ...firstPage,
            records: [createdWorkItem, ...firstPage.records],
          };
        }

        return {
          ...oldData,
          pages: updatedPages,
        };
      },
    );
  },
}));

/**
 * Update Work Item
 */
export const useUpdateWorkItemMutation = createSparMutation<
  { agentId: string },
  { workItemId: string; workItemName: string }
>()(({ sparAPIClient, queryClient, agentId }) => ({
  mutationFn: async ({ workItemId, workItemName }) => {
    const response = await sparAPIClient.queryAgentServer('patch', '/api/v2/work-items/{work_item_id}', {
      params: { path: { work_item_id: workItemId } },
      body: { work_item_name: workItemName },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to update work item', {
        code: response.code,
        resource: ResourceType.WorkItem,
      });
    }

    return response.data;
  },
  onSuccess: (updatedWorkItem, { workItemId }) => {
    queryClient.setQueryData(workItemQueryKey(workItemId), updatedWorkItem);

    queryClient.setQueriesData<InfiniteData<WorkItemsListResponse>>(
      {
        queryKey: infiniteWorkItemsQueryKeyPrefix({ agentId }),
        exact: false,
      },
      (oldData) => {
        if (!oldData) {
          return oldData;
        }

        return {
          ...oldData,
          pages: oldData.pages.map((page) => ({
            ...page,
            records: page.records?.map((workItem) =>
              workItem.work_item_id === workItemId ? updatedWorkItem : workItem,
            ),
          })),
        };
      },
    );
  },
}));

/**
 * Restart Work Item
 */
export const useRestartWorkItemMutation = createSparMutation<{ workItemId: string }, Record<string, never>>()(
  ({ workItemId, sparAPIClient, queryClient }) => ({
    mutationFn: async () => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/work-items/{work_item_id}/restart', {
        params: { path: { work_item_id: workItemId } },
      });

      if (!response.success) {
        throw new QueryError('Failed to restart work item', {
          code: response.code,
          resource: ResourceType.WorkItem,
        });
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workItemQueryKey(workItemId) });
      queryClient.invalidateQueries({ queryKey: ['work-items'] });
    },
  }),
);

/**
 * Complete Work Item
 */
export const useCompleteWorkItemMutation = createSparMutation<{ workItemId: string }, Record<string, never>>()(
  ({ workItemId, sparAPIClient, queryClient }) => ({
    mutationFn: async () => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/work-items/{work_item_id}/complete', {
        params: { path: { work_item_id: workItemId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to complete work item', {
          code: response.code,
          resource: ResourceType.WorkItem,
        });
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workItemQueryKey(workItemId) });
      queryClient.invalidateQueries({ queryKey: ['work-items'] });
    },
  }),
);

/**
 * Work Items Summary
 */
export type AgentWorkItemsSummary = {
  agent_id: string;
  agent_name: string;
  work_items_status_counts: Partial<Record<WorkItemStatus, number>>;
};

export const workItemsSummaryQueryKey = ['work-items-summary'];

export const workItemsSummaryQueryOptions = createSparQueryOptions()(({ sparAPIClient }) => ({
  queryKey: workItemsSummaryQueryKey,
  queryFn: async (): Promise<AgentWorkItemsSummary[]> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/work-items/summary', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch work items summary', {
        code: response.code,
        resource: ResourceType.WorkItem,
      });
    }

    return response.data;
  },
}));

export const useWorkItemsSummaryQuery = createSparQuery(workItemsSummaryQueryOptions);

/**
 * Work Item Executors Status
 */
export type WorkItemTaskStatusResponse = components['schemas']['WorkItemTaskStatusResponse'];
export type WorkItemTaskStatusResponseItem = components['schemas']['WorkItemTaskStatusResponseItem'];

export const workItemExecutorsStatusQueryKey = () => ['work-item-executors-status'];

export const workItemExecutorsStatusQueryOptions = createSparQueryOptions()(({ sparAPIClient }) => ({
  queryKey: workItemExecutorsStatusQueryKey(),
  queryFn: async (): Promise<WorkItemTaskStatusResponse> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/work-items/status', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch work item executors status', {
        code: response.code,
        resource: ResourceType.WorkItem,
      });
    }

    return response.data;
  },
}));

export const useWorkItemExecutorsStatusQuery = createSparQuery(workItemExecutorsStatusQueryOptions);

import { components } from '@sema4ai/agent-server-interface';
import { asyncForLoop } from '@sema4ai/robocloud-shared-utils';
import { useEffect, useState } from 'react';

import { createSparMutation, createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';

type WorkItem = components['schemas']['WorkItem'];
type CreateWorkItemPayload = components['schemas']['CreateWorkItemPayload'];

/**
 * List Work items
 */
export const workItemsQueryKey = (agentId?: string) => ['work-items', agentId || 'all'];

export const workItemsQueryOptions = createSparQueryOptions<{ agentId?: string }>()(({ sparAPIClient, agentId }) => ({
  queryKey: workItemsQueryKey(agentId),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/work-items/', {
      params: { query: { agent_id: agentId } },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch threads', {
        code: response.code,
        resource: ResourceType.WorkItem,
      });
    }

    return response.data.records;
  },
}));

export const useWorkItemsQuery = createSparQuery(workItemsQueryOptions);

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

export const useWorkItemQuery = ({ workItemId }: { workItemId: string }) => {
  const [refetchInterval, setRefetchInterval] = useState<number | undefined>(undefined);
  const query = createSparQuery(workItemQueryOptions)({ workItemId }, { refetchInterval });

  useEffect(() => {
    setRefetchInterval(!query.data?.thread_id ? 2000 : undefined);
  }, [query.data]);

  return query;
};

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

      // Updating query cache with new data
      queryClient.setQueryData(workItemsQueryKey(agentId), (data?: WorkItem[]) => {
        return [response.data, ...(data || [])];
      });

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
}));

import { useEffect, useState } from 'react';
import { components } from '@sema4ai/agent-server-interface';

import { createSparMutation, createSparQuery, createSparQueryOptions } from './shared';
import { SparAPIClient } from '../api';

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
      throw new Error(response.message || 'Failed to fetch threads');
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
        throw new Error(response.message || 'Failed to fetch work item');
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

/**
 * Create Work Item
 */
const uploadWorkItemFile = async (sparAPIClient: SparAPIClient, file: File, workItemId?: string) => {
  return sparAPIClient.queryAgentServer('post', '/api/v2/work-items/upload-file', {
    params: { query: workItemId ? { work_item_id: workItemId } : {} },
    body: { file: file as unknown as string },
    bodySerializer(body: { file: string }) {
      const formData = new FormData();
      formData.append('file', body.file);
      return formData;
    },
  });
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
    // Upload files
    if (files && files?.length > 0) {
      const firstFileResponse = await uploadWorkItemFile(sparAPIClient, files[0]);

      if (!firstFileResponse?.success || !firstFileResponse?.data?.work_item_id) {
        throw new Error('Failed to get Work Item ID from file upload');
      }

      const workItemId = String(firstFileResponse.data.work_item_id);

      const remainingFiles = files.slice(1);
      const uploadPromises = remainingFiles.map(async (file) => {
        return uploadWorkItemFile(sparAPIClient, file, workItemId);
      });

      try {
        await Promise.all(uploadPromises);
      } catch (error) {
        throw new Error('Failed to upload some files');
      }
    }

    const body: CreateWorkItemPayload = {
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

    // Add payload if provided; JSON validity is enforced by the form schema
    if (payload && payload.trim()) {
      const parsedPayload = JSON.parse(payload);
      body.payload = parsedPayload;
    }

    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/work-items/', {
      body,
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to create work item');
    }

    queryClient.setQueryData(workItemsQueryKey(agentId), (data?: WorkItem[]) => {
      return [response.data, ...(data || [])];
    });

    return response.data;
  },
}));

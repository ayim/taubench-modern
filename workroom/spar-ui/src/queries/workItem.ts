import type { components } from '@sema4ai/agent-server-interface';
import { createSparMutation } from './shared';

type CreateWorkItemPayload = components['schemas']['CreateWorkItemPayload'];

// Create work item mutation
export const useCreateWorkItemMutation = createSparMutation<
  { agentId: string },
  { payload: CreateWorkItemPayload }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ payload }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/work-items/', {
      body: payload,
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to create work item');
    }

    return response.data;
  },
}));

// Upload work item file mutation
export const useUploadWorkItemFileMutation = createSparMutation<
  Record<string, never>,
  { file: File; workItemId?: string }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ file, workItemId }) => {
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
      throw new Error(response.message || 'Failed to upload file');
    }

    return response.data;
  },
}));

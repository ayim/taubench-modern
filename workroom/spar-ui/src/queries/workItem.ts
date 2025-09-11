import type { components } from '@sema4ai/agent-server-interface';

import { createSparMutation } from './shared';
import { SparAPIClient } from '../api';

type CreateWorkItemPayload = components['schemas']['CreateWorkItemPayload'];

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

// Create work item mutation
export const useCreateWorkItemMutation = createSparMutation<
  { agentId: string },
  {
    message: string;
    payload?: string;
    files?: File[];
  }
>()(({ agentId, sparAPIClient }) => ({
  mutationFn: async ({ files, message, payload }) => {
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

    return response.data;
  },
}));

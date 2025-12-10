import { Agent } from '@sema4ai/agent-server-interface';

import { createSparMutation, QueryError, ResourceType } from './shared';

export const useReadPackageMutation = createSparMutation<object, { formData: FormData }>()(({ sparAPIClient }) => ({
  mutationFn: async ({ formData }): Promise<Agent> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/package/read', {
      params: {},
      body: formData as never,
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to read package', {
        code: response.code,
        resource: ResourceType.Agent,
      });
    }

    return response.data as Agent;
  },
}));

import { components } from '@sema4ai/agent-server-interface';

import { createSparMutation, QueryError, ResourceType } from './shared';

export const useReadPackageMutation = createSparMutation<object, { formData: FormData }>()(({ agentAPIClient }) => ({
  mutationFn: async ({ formData }): Promise<components['schemas']['ReadAgentPackageResult']> => {
    const response = await agentAPIClient.agentFetch('post', '/api/v2/package/read', {
      params: {},
      body: formData as never,
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to read package', {
        code: response.code,
        resource: ResourceType.Agent,
      });
    }

    return response.data;
  },
}));

export const usePackageMetadataMutation = createSparMutation<object, { formData: FormData }>()(
  ({ agentAPIClient }) => ({
    mutationFn: async ({ formData }): Promise<components['schemas']['AgentPackageMetadata']> => {
      const response = await agentAPIClient.agentFetch('post', '/api/v2/package/metadata', {
        params: {},
        body: formData as never,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to generate package metadata', {
          code: response.code,
          resource: ResourceType.Agent,
        });
      }

      return response.data.data as components['schemas']['AgentPackageMetadata'];
    },
  }),
);

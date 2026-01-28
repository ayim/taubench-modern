import type { ServerResponse } from '@sema4ai/agent-server-interface';
import { createSparMutation, QueryError, ResourceType } from './shared';

export type AgentPackageInspectionResponse = ServerResponse<'post', '/api/v2/package/inspect/agent'>['data'];

export const useInspectAgentPackageMutation = createSparMutation<object, { formData: FormData }>()(
  ({ agentAPIClient }) => ({
    mutationFn: async ({ formData }) => {
      const response = await agentAPIClient.agentFetch('post', '/api/v2/package/inspect/agent', {
        params: {},
        body: formData as never,
      });
      if (!response.success) {
        throw new QueryError(response.message, { code: response.code, resource: ResourceType.Agent });
      }
      return response.data;
    },
  }),
);

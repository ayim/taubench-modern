import type { ServerResponse } from '@sema4ai/agent-server-interface';
import { SparAPIClient } from '../api';
import { createSparMutation, QueryError, ResourceType } from './shared';

export type AgentPackageInspectionResponse = ServerResponse<'post', '/api/v2/package/inspect/agent'>['data'];

export const useInspectAgentPackageMutation = createSparMutation<
  { sparAPIClient: SparAPIClient },
  { formData: FormData }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ formData }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/package/inspect/agent', {
      params: {},
      body: formData as never,
    });
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Agent });
    }
    return response.data;
  },
}));

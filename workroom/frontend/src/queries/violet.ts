import { components } from '@sema4ai/agent-server-interface';

import { VIOLET_AGENT_METADATA } from '~/constants/violetAgent';
import { createSparQuery, createSparQueryOptions } from './shared';

const violetAgentQueryKey = ['violetAgent', JSON.stringify(VIOLET_AGENT_METADATA)];

export const getVioletAgentQueryOptions = createSparQueryOptions<object>()(({ agentAPIClient }) => ({
  queryKey: violetAgentQueryKey,
  queryFn: async (): Promise<components['schemas']['AgentCompat']> => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/agents/search/by-metadata', {
      params: { query: VIOLET_AGENT_METADATA } as never,
      errorMsg: 'Failed to locate project violet agent',
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to locate project violet agent');
    }

    const [agent] = response.data || [];

    if (!agent) {
      throw new Error('Project Violet agent not found');
    }

    return agent;
  },
}));

export const useVioletAgentQuery = createSparQuery(getVioletAgentQueryOptions);

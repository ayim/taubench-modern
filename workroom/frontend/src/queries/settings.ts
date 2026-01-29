import { useMutation } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';
import { sequentialMap } from '@sema4ai/shared-utils';
import { AgentServerConfigType } from '~/lib/AgentAPIClient';
import { createSparQueryOptions } from './shared';

export const getGetConfigQueryKey = () => ['config'];

export const getGetConfigQueryOptions = createSparQueryOptions()(({ agentAPIClient }) => ({
  queryKey: getGetConfigQueryKey(),
  queryFn: async () => {
    return agentAPIClient.agentFetch('get', '/api/v2/config/', {
      params: {},
      errorMsg: 'Config Not Found',
    });
  },
}));

export const useUpdateConfigMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useMutation({
    mutationFn: async ({
      config,
    }: {
      tenantId: string;
      config: { config_type: AgentServerConfigType; current_value: string }[];
    }) => {
      const results = await sequentialMap(config, async (configPair) => {
        return agentAPIClient.agentFetch('post', '/api/v2/config/', {
          body: configPair,
          errorMsg: 'Failed to update settings',
        });
      });

      // Check if any of the API calls failed
      const failedResult = results.find((result) => !result.success);
      if (failedResult && !failedResult.success) {
        throw new Error(failedResult.message);
      }

      return {
        numberOfUpdatedSettings: config.length,
      };
    },
  });
};

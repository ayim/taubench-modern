import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';
import { sequentialMap } from '@sema4ai/shared-utils';
import { AgentServerConfigType } from '~/lib/AgentAPIClient';
import { createSparQuery, createSparQueryOptions } from './shared';

export const getGetConfigQueryKey = () => ['config'];

export const getGetConfigQueryOptions = createSparQueryOptions()(({ agentAPIClient }) => ({
  queryKey: getGetConfigQueryKey(),
  queryFn: async () => {
    const result = await agentAPIClient.agentFetch('get', '/api/v2/config/', {
      params: {},
      errorMsg: 'Config Not Found',
    });

    if (!result.success) {
      throw new Error(result.message);
    }

    return result.data;
  },
}));

export const useConfigQuery = createSparQuery(getGetConfigQueryOptions);

export const useSetDefaultLLMMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (platformId: string) => {
      const result = await agentAPIClient.agentFetch('post', '/api/v2/config/', {
        body: {
          config_type: 'DEFAULT_LLM_PLATFORM_PARAMS_ID' as AgentServerConfigType,
          current_value: platformId,
        },
        errorMsg: 'Failed to set default LLM',
      });

      if (!result.success) {
        throw new Error(result.message);
      }

      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: getGetConfigQueryKey() });
    },
  });
};

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

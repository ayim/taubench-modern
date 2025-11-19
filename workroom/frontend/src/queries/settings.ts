import { queryOptions, useMutation } from '@tanstack/react-query';
import { QueryProps } from './shared';
import { useRouteContext } from '@tanstack/react-router';
import { sequentialMap } from '@sema4ai/robocloud-shared-utils';
import { AgentServerConfigType } from '~/lib/AgentAPIClient';

export const getGetConfigQueryKey = (tenantId: string) => [tenantId, 'config'];

export const getGetConfigQueryOptions = ({
  tenantId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: getGetConfigQueryKey(tenantId),
    queryFn: async () => {
      return await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/config/', {
        params: {},
        errorMsg: 'Config Not Found',
      });
    },
  });

export const useUpdateConfigMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useMutation({
    mutationFn: async ({
      tenantId,
      config,
    }: {
      tenantId: string;
      config: { config_type: AgentServerConfigType; current_value: string }[];
    }) => {
      const results = await sequentialMap(config, async (configPair) => {
        return await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/config/', {
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

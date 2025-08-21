import { queryOptions, useMutation } from '@tanstack/react-query';
import { QueryProps } from './shared';
import { useRouteContext } from '@tanstack/react-router';
import { sequentialMap } from '@sema4ai/robocloud-shared-utils';

export const getGetConfigQueryKey = (tenantId: string) => [tenantId, 'config'];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type REMOVE_ME_WHEN_2_0_28_INTERFACE_IS_PUBLISHED = any;
type REMOVE_ME_TOO = { config_type: string; config_value: string };

export const getGetConfigQueryOptions = ({
  tenantId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: getGetConfigQueryKey(tenantId),
    queryFn: async () => {
      return (await agentAPIClient.agentFetch(
        tenantId,
        'get',
        '/api/v2/config/' as REMOVE_ME_WHEN_2_0_28_INTERFACE_IS_PUBLISHED,
        {
          params: { path: {} },
          errorMsg: 'Config Not Found',
        },
      )) as REMOVE_ME_TOO[];
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
      config: { config_type: string; current_value: string }[];
    }) => {
      await sequentialMap(config, async (configPair) => {
        return await agentAPIClient.agentFetch(
          tenantId,
          'post',
          '/api/v2/config/' as REMOVE_ME_WHEN_2_0_28_INTERFACE_IS_PUBLISHED,
          {
            body: configPair,
            errorMsg: 'Failed to update settings',
          },
        );
      });

      return {
        numberOfUpdatedSettings: config.length,
      };
    },
  });
};

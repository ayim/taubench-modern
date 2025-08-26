import { queryOptions, useMutation } from '@tanstack/react-query';
import { QueryProps } from './shared';
import { useRouteContext } from '@tanstack/react-router';

export const getGetDocumentIntelligenceQueryKey = (tenantId: string) => [tenantId, 'documentIntelligence'];

export const getGetDocumentIntelligenceQueryOptions = ({
  tenantId,
  agentAPIClient,
}: QueryProps<{
  tenantId: string;
}>) =>
  queryOptions({
    queryKey: getGetDocumentIntelligenceQueryKey(tenantId),
    queryFn: async () => {
      return await agentAPIClient.getDocumentIntelligenceConfiguration({ tenantId });
    },
  });

export const useUpsertDocumentIntelligenceConfigMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useMutation({
    mutationFn: async ({
      tenantId,
      configuration,
    }: {
      tenantId: string;
      configuration: { reductoApiKey: string; reductoEndpoint: string; postgresConnectionUrl: string };
    }) => {
      await agentAPIClient.SPAR_upsertDocumentIntelligenceConfiguration({ tenantId, configuration });
    },
  });
};

export const useClearDocumentIntelligenceConfigMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  return useMutation({
    mutationFn: async ({ tenantId }: { tenantId: string }) => {
      await agentAPIClient.clearDocumentIntelligenceConfiguration({ tenantId });
    },
  });
};

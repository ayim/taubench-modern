import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';
import { dataConnectionsQueryKey } from '@sema4ai/spar-ui/queries';
import { QueryProps } from './shared';

export const documentIntelligenceQueryKey = (tenantId: string) => [tenantId, 'documentIntelligence'];

export const getDocumentIntelligenceQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: documentIntelligenceQueryKey(tenantId),
    queryFn: () => agentAPIClient.getDocumentIntelligenceConfiguration({ tenantId }),
  });

export const useUpsertDocumentIntelligenceConfigMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tenantId,
      configuration,
    }: {
      tenantId: string;
      configuration: { reductoApiKey: string; reductoEndpoint: string; dataConnectionId: string };
    }) => {
      await agentAPIClient.SPAR_upsertDocumentIntelligenceConfiguration({ tenantId, configuration });
    },
    onSuccess: async (_, { tenantId }) => {
      await queryClient.refetchQueries({ queryKey: documentIntelligenceQueryKey(tenantId) });
      await queryClient.refetchQueries({ queryKey: dataConnectionsQueryKey() });
    },
  });
};

export const useClearDocumentIntelligenceConfigMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ tenantId }: { tenantId: string }) => {
      await agentAPIClient.clearDocumentIntelligenceConfiguration({ tenantId });
    },
    onSuccess: async (_, { tenantId }) => {
      await queryClient.refetchQueries({ queryKey: documentIntelligenceQueryKey(tenantId) });
      await queryClient.refetchQueries({ queryKey: dataConnectionsQueryKey() });
    },
  });
};

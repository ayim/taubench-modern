import { useMutation } from '@tanstack/react-query';
import { useRouteContext } from '@tanstack/react-router';

export const useDeleteOAuthConnection = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  return useMutation({
    mutationFn: async ({
      tenantId,
      agentId,
      connectionId,
    }: {
      tenantId: string;
      agentId: string;
      connectionId: string;
    }) => {
      return agentAPIClient.deleteOAuthConnection({
        tenantId,
        agentId,
        connectionId,
      });
    },
  });
};

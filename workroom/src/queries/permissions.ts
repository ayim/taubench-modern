import { AgentOAuthPermission } from '@sema4ai/workroom-interface';
import { queryOptions } from '@tanstack/react-query';
import { QueryProps } from './shared';

export const getListAgentPermissionsQueryKey = (agentId: string) => ['agentPerrmissions', agentId];

export const getListAgentPermissionsQueryOptions = ({
  agentId,
  tenantId,
  agentAPIClient,
  initialData,
}: QueryProps<{
  tenantId: string;
  agentId: string;
  initialData?: AgentOAuthPermission[];
}>) =>
  queryOptions({
    queryKey: getListAgentPermissionsQueryKey(agentId),
    queryFn: async (): Promise<AgentOAuthPermission[]> => {
      const permissions = await agentAPIClient.getAgentPermissions({ tenantId, agentId });
      return permissions;
    },
    initialData: initialData ?? [],
  });

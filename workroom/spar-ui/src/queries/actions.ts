import { createSparQuery, createSparQueryOptions } from './shared';

export const agentActionPackagesQueryKey = (agentId: string) => ['actions', agentId];

export const agentActionPackagesQueryOptions = createSparQueryOptions<{ agentId: string }>()(
  ({ sparAPIClient, agentId }) => ({
    queryKey: agentActionPackagesQueryKey(agentId),
    queryFn: async () => {
      return sparAPIClient.getActionDetails?.({ agentId });
    },
  }),
);

export const useAgentActionPackagesQuery = createSparQuery(agentActionPackagesQueryOptions);

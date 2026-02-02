import { useAgentUserInterfacesQuery } from '~/queries/agents';
import { getDocIntelInterfaces } from '../constants/interfaceLabels';

/**
 * Hook to get Document Intelligence capabilities for an agent
 * Wraps useAgentUserInterfacesQuery and filters to DocIntel interfaces
 *
 * @param agentId - The agent ID to query capabilities for
 * @returns Object with DocIntel interfaces and helper flags
 */
export const useAgentDocIntelCapabilities = (agentId: string) => {
  const {
    data: userInterfaces,
    isLoading,
    error,
  } = useAgentUserInterfacesQuery(
    { agentId },
    {
      enabled: Boolean(agentId),
    },
  );

  const docIntelInterfaces = getDocIntelInterfaces(userInterfaces);

  return {
    // Filtered DocIntel interfaces
    docIntelInterfaces,
    isLoading,
    error,

    // Raw data if needed
    allUserInterfaces: userInterfaces,
  };
};

/**
 * Label mapping for Document Intelligence interface types
 * Maps API enum values to user-friendly display strings
 */
export const DOC_INTEL_INTERFACE_LABELS: Record<string, string> = {
  'di-parse-only': 'Parse',
  // 'parse-only-v1': 'Parse Only V1', // Use this for legacy flow. (DocumentIntelligenceDialog.tsx)
  'di-extract-only': 'Extract',
  'di-create-data-model': 'Create Data Model',
} as const;

/**
 * Get user-friendly label for a Document Intelligence interface type
 * @param interfaceType - The interface type enum value (e.g., 'di-parse-only')
 * @returns User-friendly label, or the raw interface type if not found
 */
export const getDocIntelLabel = (interfaceType: string): string => {
  return DOC_INTEL_INTERFACE_LABELS[interfaceType] || interfaceType;
};

const docIntelDefaultCapabilities = ['di-extract-only', 'di-parse-only'];

/**
 * This enabled doc intel parse and extract for all agents
 * - by merging existing interfaces with default capabilities
 */
const mergeInterfacesWithDefaultCapabilities = (userInterfaces: string[] | undefined = []): string[] => [
  ...new Set([...docIntelDefaultCapabilities, ...userInterfaces]),
];

/**
 * Get all Document Intelligence interfaces from a list of user interfaces
 * @param userInterfaces - Array of interface strings from useAgentUserInterfacesQuery
 * @returns Filtered array containing only known DocIntel interfaces
 */
export const getDocIntelInterfaces = (userInterfaces: string[] | undefined): string[] => {
  return mergeInterfacesWithDefaultCapabilities(userInterfaces).filter(
    (ui) => typeof DOC_INTEL_INTERFACE_LABELS[ui] === 'string',
  );
};

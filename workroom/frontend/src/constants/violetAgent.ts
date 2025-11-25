export const VIOLET_AGENT_METADATA = {
  project: 'violet',
  visibility: 'hidden',
} as const;

// Keep in sync with server/src/agent_platform/server/preinstalled_agents.py
// (Which should be very stable... not likely to change soon)
export type VioletAgentMetadata = typeof VIOLET_AGENT_METADATA;

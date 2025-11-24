export interface AgentContext {
  /** Raw context for the agent (optional) */
  raw?: string;

  // Agent Model
  agentModel?: string;
  agentModelProvider?: string;

  // Agent Context
  agentName?: string;
  agentDescription?: string;
  agentRunbook?: string;
  agentConversationStarter?: string;
  agentQuestionGroups?: any[];

  // Actions
  selectedActionPackages?: any[];
  availableActionPackages?: any[];

  // MCP Servers
  selectedMcpServers?: any[];
  availableMcpServers?: any[];
}

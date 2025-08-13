// Agent prompt module exports
export * from './agent-prompt';

// Ephemeral agent module exports (with explicit re-exports to avoid naming conflicts)
export {
  // Types
  AgentArchitecture as EphemeralAgentArchitecture,
  PlatformConfig as EphemeralPlatformConfig,
  ActionPackage as EphemeralActionPackage,
  McpServer as EphemeralMcpServer,
  QuestionGroup as EphemeralQuestionGroup,
  ObservabilityConfig as EphemeralObservabilityConfig,
  EphemeralAgentConfig,
  AgentMessage,
  EphemeralStreamRequest,
  EphemeralEventType,
  BaseEphemeralEvent,
  AgentReadyEvent,
  AgentFinishedEvent,
  AgentErrorEvent,
  MessageEvent,
  DataEvent,
  EphemeralEvent,
  EphemeralEventHandlers,
  EphemeralAgentClientConfig,
  CreateEphemeralStreamOptions,
  EphemeralStreamResult,
  EphemeralAgentValidationError,
  EphemeralAgentStreamError,
  createUserMessage,

  // Client and utilities
  EphemeralAgentClient,
  createEphemeralAgentClient,
  createBasicAgentConfig,
  createHumanMessage,
  createSystemMessage,
  isEphemeralAgentStreamError,
  getEphemeralAgentErrorMessage,
} from './agent-ephemeral';

// SDK module exports
// Explicitly re-export to avoid ambiguity with './agent-prompt'
export {
  // Types
  ScenarioTool,
  Scenario,
  Context,
  // Config Functions & Types
  initializeSDK,
  getSDKConfig,
  SaiSDKConfig,
  SaiSDKConfiguration,
  // Tool Functions & Types
  createTool,
  validateTool,
  // Scenario Functions
  ScenarioDefinitionBuilder,
  ScenarioBuilder,
  createScenario,
  createDefaultContext,
  createConservativeContext,
  createBalancedContext,
  createCreativeContext,
  cloneScenario,
  mergeContexts,
  getScenarioSummary,
  validateScenario,
  validateContext,
} from './sdk/index';

/**
 * Types for ephemeral agent streaming
 * Based on agent-platform WebSocket streaming API
 */

import { ToolCategory } from '../tools';
import { PlatformConfig } from '../platform-config';

/**
 * Agent architecture configuration
 */
export interface AgentArchitecture {
  /** Architecture name */
  name: string;
  /** Architecture version */
  version: string;
}

/**
 * Action package configuration
 */
export interface ActionPackage {
  /** Package name */
  name: string;
  /** Organization name */
  organization: string;
  /** Package version */
  version: string;
  /** Package actions */
  actions?: { name: string; description: string }[];
  /** Package URL */
  url?: string;
  /** API key for the package */
  api_key?: string;
  /** Whitelist configuration */
  whitelist?: string;
}

/**
 * MCP server configuration
 */
export interface McpServer {
  /** Server configuration */
  [key: string]: any;

  tools?: { name: string; description: string }[];
}

/**
 * Question group configuration
 */
export interface QuestionGroup {
  /**
   * Title
   * @description The title of the question group.
   */
  title: string;
  /**
   * Questions
   * @description The questions in the question group.
   */
  questions?: string[];
}

/**
 * Observability configuration
 */
export interface ObservabilityConfig {
  /** Observability configuration */
  [key: string]: any;
}

/**
 * Complete ephemeral agent configuration
 */
export interface EphemeralAgentConfig {
  /** Agent name */
  name: string;
  /** Agent description */
  description: string;
  /** Agent version */
  version: string;
  /** Agent runbook/instructions */
  runbook: string;
  /** Agent architecture */
  agent_architecture: AgentArchitecture;
  /** Platform configurations */
  platform_configs: PlatformConfig[];
  /** Action packages */
  action_packages: ActionPackage[];
  /** MCP servers */
  mcp_servers: McpServer[];
  /** Question groups */
  question_groups: QuestionGroup[];
  /** Observability configurations */
  observability_configs: ObservabilityConfig[];
  /** Agent mode */
  mode: string;
  /** Extra configuration */
  extra: Record<string, any>;
  /** Advanced configuration */
  advanced_config: Record<string, any>;
  /** Metadata */
  metadata: Record<string, any>;
  /** Whether agent is public */
  public: boolean;
}

/**
 * Message format for agent conversation
 */
export interface AgentMessage {
  /** Message content */
  content: string;
  /** Message role */
  role: 'human' | 'ai' | 'system' | 'tool';
  /** Message ID */
  id?: string;
  /** Additional message properties */
  [key: string]: any;
}

/**
 * Tool definition for client-side tools
 */
export interface ToolDefinitionPayload {
  /** The name of the tool */
  name: string;
  /** The description of the tool */
  description: string;
  /** The schema of the tool input */
  input_schema: Record<string, any>;
  /** The category of the tool */
  category?: ToolCategory;
  /** The callback function for the tool */
  callback?: (input: any) => any;
}

/**
 * Payload for initiating a stream against a thread
 */
export interface InitiateStreamPayload {
  /** The agent ID of the agent that created this thread */
  agent_id: string;
  /** The ID of the thread to stream against */
  thread_id?: string | null;
  /** The name of the thread to stream against */
  name?: string | null;
  /** All messages in this thread */
  messages?: ThreadMessage[];
  /** Arbitrary thread-level metadata */
  metadata?: Record<string, any>;
  /** The tools attached to the payload from an external client */
  client_tools?: ToolDefinitionPayload[];
}

/**
 * Citation in text content
 */
export interface Citation {
  /** The URI of the document that the citation is from */
  document_uri: string;
  /** The start character index of the citation in the document */
  start_char_index: number;
  /** The end character index of the citation in the document */
  end_char_index: number;
  /** The text that is being cited (if provided, may be null) */
  cited_text?: string | null;
}

/**
 * Base interface for content deltas
 */
export interface ContentDelta {
  /** Content kind */
  kind: string;
}

/**
 * Text delta for thread text content
 */
export interface TextDelta extends ContentDelta {
  /** Content kind: always 'text' */
  kind: 'text';
}

/**
 * Thread message content types
 */
export interface ThreadTextContent {
  /** The actual text content of the message */
  text: string;
  /** The citations in the text content */
  citations: Citation[];
  /** Content kind: always 'text' */
  kind: 'text';
}

export interface ThreadQuickActionsContent {
  kind: 'action';
  actions: Array<{
    label: string;
    value: string;
  }>;
  complete?: boolean;
}

export interface ThreadVegaChartContent {
  kind: 'vega_chart';
  spec: any; // Vega-Lite specification
  complete?: boolean;
}

export interface ThreadToolUsageContent {
  kind: 'tool_usage';
  tool_name: string;
  tool_input: any;
  tool_output?: any;
  complete?: boolean;
}

export interface ThreadThoughtContent {
  kind: 'thought';
  thought: string;
  complete?: boolean;
}

export interface ThreadAttachmentContent {
  kind: 'attachment';
  filename: string;
  file_type: string;
  file_size: number;
  file_data?: string; // Base64 encoded or URL
  complete?: boolean;
}

/**
 * Union type for all thread message content types
 */
export type AnyThreadMessageContent =
  | ThreadTextContent
  | ThreadQuickActionsContent
  | ThreadVegaChartContent
  | ThreadToolUsageContent
  | ThreadThoughtContent
  | ThreadAttachmentContent;

/**
 * Thread message role type
 */
export type ThreadMessageRole = 'user' | 'agent';

/**
 * Thread message for ephemeral agent conversations
 */
export interface ThreadMessage {
  /** The contents of the thread message */
  content: AnyThreadMessageContent[];
  /** The role of the message sender */
  role: ThreadMessageRole;
  /** True when the content has finished streaming, false otherwise */
  complete?: boolean;
  /** Whether the message has been committed to the thread (saved to backing storage) */
  commited?: boolean;
  /** The time the message was created */
  created_at?: string; // ISO 8601 format
  /** The time the message was last updated */
  updated_at?: string; // ISO 8601 format
  /** The metadata associated with the message (for agent architecture use only) */
  agent_metadata?: Record<string, any>;
  /** The metadata associated with the message (for agent-server use only) */
  server_metadata?: Record<string, any>;
  /** The unique identifier for the run that created this message or null if not created by a run */
  parent_run_id?: string | null;
  /** The unique identifier for the message */
  message_id?: string;
}

/**
 * Agent mode type
 */
export type AgentMode = 'conversational' | 'worker';

/**
 * Runbook structure
 */
export interface Runbook {
  /** Raw text of the runbook */
  raw_text: string;
  /** Structured content */
  content: any[];
}

/**
 * Patch agent payload (for updating agents)
 */
export interface PatchAgentPayload {
  /** The name of the agent */
  name: string;
  /** The description of the agent */
  description: string;
}

/**
 * Agent payload for ephemeral stream (matches UpsertAgentPayload structure)
 */
export interface UpsertAgentPayload {
  /** The name of the agent */
  name: string;
  /** The description of the agent */
  description: string;
  /** The version of the agent */
  version: string;
  /** The id of the user that created the agent */
  user_id?: string | null;
  /** The platform configs this agent can use */
  platform_configs?: PlatformConfig[];
  /** The architecture details for the agent */
  agent_architecture?: AgentArchitecture | null;
  /** The raw text of the runbook */
  runbook?: string | null;
  /** The structured runbook of the agent */
  structured_runbook?: Runbook | null;
  /** The action packages this agent uses */
  action_packages?: ActionPackage[];
  /** The Model Context Protocol (MCP) servers this agent uses */
  mcp_servers?: McpServer[];
  /** The question groups of the agent */
  question_groups?: QuestionGroup[];
  /** The observability configs of the agent */
  observability_configs?: ObservabilityConfig[];
  /** The mode of the agent */
  mode?: AgentMode;
  /** Extra fields for the agent */
  extra?: Record<string, any>;
  /** The ID of the agent (alias of agent_id for backwards compatibility) */
  id?: string | null;
  /** The ID of the agent */
  agent_id?: string | null;
  /** The time the agent was created */
  created_at?: string | null; // ISO 8601 format
  /** Advanced configuration for the agent (backward compatibility) */
  advanced_config?: Record<string, any>;
  /** Metadata for the agent (backward compatibility) */
  metadata?: Record<string, any>;
  /** Model for the agent (backward compatibility) */
  model?: Record<string, any> | null;
  /** Ignored. Backward compatibility only */
  public?: boolean;
}

/**
 * Request payload for ephemeral agent streaming (matches Python EphemeralStreamPayload)
 */
export interface EphemeralStreamRequest {
  /** Agent configuration */
  agent: UpsertAgentPayload;
  /** Optional agent name override */
  name?: string | null;
  /** Initial messages */
  messages?: ThreadMessage[];
  /** Additional metadata */
  metadata?: Record<string, any>;
  /** Client-side tool definitions */
  client_tools?: ToolDefinitionPayload[];
}

/**
 * Event types from ephemeral agent stream
 */
export type EphemeralMessageEventType = 'message_content' | 'message_metadata' | 'message_begin' | 'message_end';
export type EphemeralEventType =
  | 'agent_ready'
  | 'agent_finished'
  | 'agent_error'
  | 'data'
  | 'request_tool_execution'
  | EphemeralMessageEventType;

/**
 * Base event structure
 */
export interface BaseEphemeralEvent {
  /** Event type */
  event_type: EphemeralEventType;
  /** Event timestamp */
  timestamp?: string;
}

/**
 * Agent ready event - sent when agent is created and ready
 */
export interface AgentReadyEvent extends BaseEphemeralEvent {
  event_type: 'agent_ready';
  /** Run ID */
  run_id: string;
  /** Thread ID */
  thread_id: string;
  /** Agent ID */
  agent_id: string;
  /** Timestamp */
  timestamp: string;
}

/**
 * Agent finished event - sent when agent completes
 */
export interface AgentFinishedEvent extends BaseEphemeralEvent {
  event_type: 'agent_finished';
  /** Final result or output */
  result?: any;
}

/**
 * Agent error event - sent when there's an error
 */
export interface AgentErrorEvent extends BaseEphemeralEvent {
  event_type: 'agent_error';
  /** Error message */
  error_message: string;
  /** Error code */
  error_code?: string;
  /** Additional error details */
  details?: Record<string, any>;
}

export interface Delta {
  op: string;
  path: string;
  value: any;
}

/**
 * Message event - sent for streaming messages
 */
export interface MessageEvent extends BaseEphemeralEvent {
  event_type: EphemeralMessageEventType;
  /** Message content */
  content: AnyThreadMessageContent[];
  /** Message role */
  role?: string;
  /** Message metadata */
  metadata?: Record<string, any>;
  /** Message ID */
  message_id?: string;
  /** Thread ID */
  thread_id?: string;
  /** Agent ID */
  agent_id?: string;
  /** Delta */
  delta: Delta;
  /** Complete */
  complete?: boolean;
  /** Committed */
  committed?: boolean;
  /** Parent run ID */
  parent_run_id?: string;
  /** Data */
  data?: Record<string, any>;
}

/**
 * Data event - sent for streaming data
 */
export interface DataEvent extends BaseEphemeralEvent {
  event_type: 'data';
  /** Data payload */
  data: any;
}

export interface RequestToolExecutionEvent extends BaseEphemeralEvent {
  event_type: 'request_tool_execution';
  input_raw: string;
  timestamp: string;
  tool_call_id: string;
  tool_name: string;
}

/**
 * Union type for all ephemeral events
 */
export type EphemeralEvent =
  | AgentReadyEvent
  | AgentFinishedEvent
  | AgentErrorEvent
  | MessageEvent
  | DataEvent
  | RequestToolExecutionEvent;

/**
 * Event handlers for ephemeral agent streaming
 */
export interface EphemeralEventHandlers {
  /** Called when agent is ready */
  onAgentReady?: (event: AgentReadyEvent) => void;
  /** Called when agent finishes */
  onAgentFinished?: (event: AgentFinishedEvent) => void;
  /** Called when there's an error */
  onAgentError?: (event: AgentErrorEvent) => void;
  /** Called for streaming messages */
  onMessage?: (event: MessageEvent) => void;
  /** Called for streaming where message is started */
  onMessageBegin?: (event: MessageEvent) => void;
  /** Called for streaming where message is content */
  onMessageContent?: (event: MessageEvent) => void;
  /** Called for streaming where message is finished */
  onMessageEnd?: (event: MessageEvent) => void;
  /** Called for streaming data */
  onData?: (event: DataEvent) => void;
  /** Called for any event */
  onEvent?: (event: EphemeralEvent) => void;
  /** Called when connection opens */
  onOpen?: () => void;
  /** Called when connection closes */
  onClose?: (code?: number, reason?: string) => void;
}

/**
 * Configuration for the ephemeral agent client
 */
export interface EphemeralAgentClientConfig {
  /** Base URL for the agent platform WebSocket API */
  baseUrl: string;
  /** API key for authentication (if needed) */
  apiKey?: string;
  /** Connection timeout in milliseconds */
  timeout?: number;
  /** Additional headers to include in WebSocket connection */
  headers?: Record<string, string>;
  /** Verbose */
  verbose?: boolean;
}

/**
 * Options for creating an ephemeral agent stream
 */
export interface CreateEphemeralStreamOptions {
  /** Agent configuration */
  agent: UpsertAgentPayload;
  /** Optional agent name override */
  name?: string | null;
  /** Initial messages */
  messages?: ThreadMessage[];
  /** Additional metadata */
  metadata?: Record<string, any>;
  /** Client-side tool definitions */
  client_tools?: ToolDefinitionPayload[];
  /** Event handlers */
  handlers: EphemeralEventHandlers;
}

/**
 * Result of creating an ephemeral stream
 */
export interface EphemeralStreamResult {
  /** WebSocket connection */
  websocket: WebSocket;
  /** Agent IDs from agent_ready event */
  agentIds?: {
    run_id: string;
    thread_id: string;
    agent_id: string;
  };
  /** Close the connection */
  close: () => void;
  /** Send a message to the agent */
  sendMessage: (message: ThreadMessage) => void;
}

/**
 * Validation error for ephemeral agent configuration
 */
export class EphemeralAgentValidationError extends Error {
  constructor(
    message: string,
    public field?: string,
  ) {
    super(message);
    this.name = 'EphemeralAgentValidationError';
  }
}

/**
 * Error for ephemeral agent streaming
 */
export class EphemeralAgentStreamError extends Error {
  constructor(
    message: string,
    public code?: string,
    public details?: Record<string, any>,
  ) {
    super(message);
    this.name = 'EphemeralAgentStreamError';
  }
}

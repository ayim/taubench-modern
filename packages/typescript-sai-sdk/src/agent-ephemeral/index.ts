/**
 * Ephemeral Agent SDK
 *
 * This module provides utilities for creating and managing ephemeral agents
 * via WebSocket streaming. Ephemeral agents are temporary agents that can be
 * quickly spun up for specific tasks and automatically cleaned up.
 *
 * @example
 * ```typescript
 * import {
 *   createEphemeralAgentClient,
 *   createBasicAgentConfig,
 *   createUserMessage,
 *   createCitation
 * } from '@sema4ai/sai-sdk/agent-ephemeral';
 *
 * const client = createEphemeralAgentClient({
 *   baseUrl: 'https://api.example.com'
 * });
 *
 * // Create a basic agent configuration
 * const agentConfig = createBasicAgentConfig({
 *   name: 'temp-assistant',
 *   description: 'A temporary assistant agent',
 *   runbook: 'You are a helpful assistant',
 *   openai_api_key: 'your-openai-key'
 * });
 *
 * // Create an ephemeral agent stream
 * const stream = await client.createStream({
 *   agent: agentConfig,
 *   messages: [{
 *     role: 'user',
 *     content: [{
 *       content_type: 'text',
 *       content_id: 'msg-1',
 *       text: 'Hello, can you help me?'
 *     }]
 *   }],
 *   handlers: {
 *     onAgentReady: (event) => {
 *       console.log('Agent ready:', event.agent_id);
 *     },
 *     onMessage: (event) => {
 *       console.log('Message:', event.content);
 *     },
 *     onAgentFinished: () => {
 *       console.log('Agent finished');
 *       stream.close();
 *     },
 *     onAgentError: (event) => {
 *       console.error('Agent error:', event.error_message);
 *     }
 *   }
 * });
 * ```
 */

// Export all types
export * from './types';

// Export client and utilities
export {
  EphemeralAgentClient,
  createEphemeralAgentClient,
  createBasicAgentConfig,
  createUserMessage,
  createAgentMessage,
  createUserMessageWithCitations,
  createAgentMessageWithCitations,
  createCitation,
  createHumanMessage,
  createSystemMessage,
  isEphemeralAgentStreamError,
  getEphemeralAgentErrorMessage,
} from './client';

// Re-export commonly used types for convenience
export type {
  EphemeralAgentConfig,
  UpsertAgentPayload,
  PatchAgentPayload,
  AgentMode,
  Runbook,
  ThreadMessage,
  ThreadMessageRole,
  AnyThreadMessageContent,
  ThreadTextContent,
  ThreadQuickActionsContent,
  ThreadVegaChartContent,
  ThreadToolUsageContent,
  ThreadThoughtContent,
  ThreadAttachmentContent,
  Citation,
  ContentDelta,
  TextDelta,
  ToolDefinitionPayload,
  ToolCategory,
  InitiateStreamPayload,
  AgentMessage,
  EphemeralEventHandlers,
  CreateEphemeralStreamOptions,
  EphemeralStreamResult,
  EphemeralAgentClientConfig,
  EphemeralEvent,
  AgentReadyEvent,
  AgentFinishedEvent,
  AgentErrorEvent,
  MessageEvent,
  DataEvent,
  EphemeralStreamRequest,
} from './types';

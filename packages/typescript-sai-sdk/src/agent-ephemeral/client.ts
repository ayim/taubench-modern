/**
 * Ephemeral Agent Streaming Client
 * Provides WebSocket-based streaming for ephemeral agents
 */

import { logger } from '../logger';
import {
  EphemeralAgentClientConfig,
  CreateEphemeralStreamOptions,
  EphemeralStreamResult,
  EphemeralStreamRequest,
  EphemeralEvent,
  AgentReadyEvent,
  AgentFinishedEvent,
  AgentErrorEvent,
  MessageEvent,
  DataEvent,
  EphemeralAgentStreamError,
  ThreadMessage,
  UpsertAgentPayload,
  Citation,
} from './types';

/**
 * Client for creating and managing ephemeral agent streams
 */
export class EphemeralAgentClient {
  private config: EphemeralAgentClientConfig;

  constructor(config: EphemeralAgentClientConfig) {
    this.config = {
      timeout: 30000, // 30 seconds default
      ...config,
    };
  }

  /**
   * Create a new ephemeral agent stream
   */
  async createStream(options: CreateEphemeralStreamOptions): Promise<EphemeralStreamResult> {
    const { agent, messages = [], handlers, client_tools } = options;

    // Convert HTTP URL to WebSocket URL or use existing WebSocket URL
    let wsUrl: string;
    if (this.config.baseUrl.startsWith('ws://') || this.config.baseUrl.startsWith('wss://')) {
      // Already a WebSocket URL
      wsUrl = this.config.baseUrl;
    } else if (this.config.baseUrl.startsWith('https://')) {
      // Convert HTTPS to WSS
      wsUrl = this.config.baseUrl.replace(/^https:\/\//, 'wss://');
    } else if (this.config.baseUrl.startsWith('http://')) {
      // Convert HTTP to WS
      wsUrl = this.config.baseUrl.replace(/^http:\/\//, 'ws://');
    } else {
      // Assume it's a hostname without protocol, default to ws://
      wsUrl = `ws://${this.config.baseUrl}`;
    }
    wsUrl += '/api/v2/runs/ephemeral/stream';

    return new Promise((resolve, reject) => {
      let websocket: WebSocket;
      let agentIds: EphemeralStreamResult['agentIds'];
      let isResolved = false;

      const createStreamResult = (): EphemeralStreamResult => ({
        websocket,
        agentIds,
        close: () => websocket.close(),
        sendMessage: (message: ThreadMessage) => {
          if (websocket.readyState === WebSocket.OPEN) {
            // Send the complete ThreadMessage object as the server expects for continuation
            websocket.send(JSON.stringify(message));
          }
        },
      });

      try {
        // Create WebSocket connection
        websocket = new WebSocket(wsUrl);

        // Set up event listeners
        websocket.onopen = () => {
          // Send the ephemeral stream request
          const payload: EphemeralStreamRequest = {
            agent,
            messages,
            client_tools,
          };

          websocket.send(JSON.stringify(payload));

          handlers.onOpen?.();
        };

        websocket.onmessage = (event) => {
          try {
            const data: EphemeralEvent = JSON.parse(event.data);

            // Handle specific event types
            switch (data.event_type) {
              case 'agent_ready':
                const readyEvent = data as AgentReadyEvent;
                agentIds = {
                  run_id: readyEvent.run_id,
                  thread_id: readyEvent.thread_id,
                  agent_id: readyEvent.agent_id,
                };
                handlers.onAgentReady?.(readyEvent);

                // Resolve the Promise only when agent is ready
                resolve(createStreamResult());
                break;

              case 'agent_finished':
                handlers.onAgentFinished?.(data as AgentFinishedEvent);
                break;

              case 'agent_error':
                const errorEvent = data as AgentErrorEvent;
                handlers.onAgentError?.(errorEvent);

                if (!isResolved) {
                  reject(
                    new EphemeralAgentStreamError(errorEvent.error_message, errorEvent.error_code, errorEvent.details),
                  );
                }
                break;

              case 'message':
                handlers.onMessage?.(data as MessageEvent);
                break;

              case 'data':
                handlers.onData?.(data as DataEvent);
                break;

              default:
                // Handle any other event types
                break;
            }

            // Call the general event handler
            handlers.onEvent?.(data);
          } catch (error) {
            logger.error('Error parsing WebSocket message:', error);
          }
        };

        websocket.onclose = (event) => {
          handlers.onClose?.(event.code, event.reason);

          // Only reject if Promise hasn't been resolved yet
          if (!isResolved) {
            reject(
              new EphemeralAgentStreamError('Connection closed before agent ready', 'CONNECTION_CLOSED', {
                code: event.code,
                reason: event.reason,
              }),
            );
          }
        };

        websocket.onerror = (error) => {
          if (!isResolved) {
            reject(new EphemeralAgentStreamError('WebSocket connection error', 'CONNECTION_ERROR', { error }));
          }
        };
      } catch (error) {
        if (!isResolved) {
          reject(
            new EphemeralAgentStreamError('Failed to create WebSocket connection', 'CONNECTION_FAILED', { error }),
          );
        }
      }
    });
  }

  /**
   * Update client configuration
   */
  updateConfig(newConfig: Partial<EphemeralAgentClientConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }

  /**
   * Get current client configuration
   */
  getConfig(): EphemeralAgentClientConfig {
    return { ...this.config };
  }
}

/**
 * Create a new ephemeral agent client
 */
export function createEphemeralAgentClient(config: EphemeralAgentClientConfig): EphemeralAgentClient {
  return new EphemeralAgentClient(config);
}

/**
 * Utility function to create a basic ephemeral agent configuration
 */
export function createBasicAgentConfig(options: {
  name: string;
  description: string;
  runbook: string;
  openai_api_key?: string;
  anthropic_api_key?: string;
}): UpsertAgentPayload {
  const { name, description, runbook, openai_api_key, anthropic_api_key } = options;

  // Determine platform configs based on available API keys
  const platform_configs = [];
  if (openai_api_key) {
    platform_configs.push({
      kind: 'openai',
      openai_api_key,
    });
  }
  if (anthropic_api_key) {
    platform_configs.push({
      kind: 'anthropic',
      anthropic_api_key,
    });
  }

  return {
    name,
    description,
    version: '1.0.0',
    runbook,
    agent_architecture: {
      name: 'agent_platform.architectures.default',
      version: '1.0.0',
    },
    action_packages: [],
    mcp_servers: [],
    question_groups: [],
    observability_configs: [],
    mode: 'conversational' as const,
    extra: {},
    advanced_config: {
      architecture: 'agent' as const,
      reasoning: 'enabled' as const,
      recursion_limit: 10,
      langsmith: null,
    },
    metadata: {
      mode: 'conversational' as const,
    },
    platform_configs,
    public: true,
  };
}

/**
 * Utility function to create a user message with text content
 */
export function createUserMessage(text: string, messageId?: string): ThreadMessage {
  return {
    role: 'user',
    content: [{ text, citations: [], kind: 'text' }],
    complete: true,
    message_id: messageId || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    agent_metadata: {},
    server_metadata: {},
  };
}

/**
 * Utility function to create an agent message with text content
 */
export function createAgentMessage(text: string, messageId?: string): ThreadMessage {
  return {
    role: 'agent',
    content: [
      {
        text,
        citations: [],
        kind: 'text',
      },
    ],
    complete: true,
    message_id: messageId || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    agent_metadata: {},
    server_metadata: {},
  };
}

/**
 * Utility function to create a citation
 */
export function createCitation(
  documentUri: string,
  startCharIndex: number,
  endCharIndex: number,
  citedText?: string | null,
): Citation {
  return {
    document_uri: documentUri,
    start_char_index: startCharIndex,
    end_char_index: endCharIndex,
    cited_text: citedText,
  };
}

/**
 * Utility function to create a user message with text content and citations
 */
export function createUserMessageWithCitations(
  text: string,
  citations: Citation[] = [],
  messageId?: string,
): ThreadMessage {
  return {
    role: 'user',
    content: [
      {
        text,
        citations,
        kind: 'text',
      },
    ],
    complete: true,
    message_id: messageId || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    agent_metadata: {},
    server_metadata: {},
  };
}

/**
 * Utility function to create an agent message with text content and citations
 */
export function createAgentMessageWithCitations(
  text: string,
  citations: Citation[] = [],
  messageId?: string,
): ThreadMessage {
  return {
    role: 'agent',
    content: [
      {
        text,
        citations,
        kind: 'text',
      },
    ],
    complete: true,
    message_id: messageId || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    agent_metadata: {},
    server_metadata: {},
  };
}

// Legacy aliases for backward compatibility
export const createHumanMessage = createUserMessage;
export const createSystemMessage = createAgentMessage;

/**
 * Utility function to check if an error is an EphemeralAgentStreamError
 */
export function isEphemeralAgentStreamError(error: any): error is EphemeralAgentStreamError {
  return error instanceof EphemeralAgentStreamError;
}

/**
 * Utility function to extract error message from an error
 */
export function getEphemeralAgentErrorMessage(error: any): string {
  if (isEphemeralAgentStreamError(error)) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

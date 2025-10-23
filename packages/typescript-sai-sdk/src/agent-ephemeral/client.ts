/**
 * Ephemeral Agent Streaming Client
 * Provides WebSocket-based streaming for ephemeral agents
 */

import { PlatformConfig } from '../platform-config';
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
  AgentArchitecture,
} from './types';
import { parse, Allow } from 'partial-json';

/**
 * Client for creating and managing ephemeral agent streams
 */
export class EphemeralAgentClient {
  private config: EphemeralAgentClientConfig;
  private verbose: boolean;

  constructor(config: EphemeralAgentClientConfig) {
    this.config = {
      timeout: 30000, // 30 seconds default
      ...config,
    };
    this.verbose = config.verbose || false;
  }

  /**
   * Create a new ephemeral agent stream
   */
  async createStream(options: CreateEphemeralStreamOptions): Promise<EphemeralStreamResult> {
    const { agent, messages = [], handlers, client_tools } = options;

    // Convert HTTP URL to WebSocket URL or use existing WebSocket URL
    let wsUrl: string;
    const baseUrl = this.config.baseUrl || (typeof window !== 'undefined' ? window.location.origin : '');

    if (baseUrl.startsWith('ws://') || baseUrl.startsWith('wss://')) {
      // Already a WebSocket URL
      wsUrl = baseUrl;
    } else if (baseUrl.startsWith('https://')) {
      // Convert HTTPS to WSS
      wsUrl = baseUrl.replace(/^https:\/\//, 'wss://');
    } else if (baseUrl.startsWith('http://')) {
      // Convert HTTP to WS
      wsUrl = baseUrl.replace(/^http:\/\//, 'ws://');
    } else {
      // Assume it's a hostname without protocol, default to ws://
      wsUrl = `ws://${baseUrl}`;
    }
    wsUrl += '/api/v2/runs/ephemeral/stream';

    logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Connecting to WebSocket URL: ${wsUrl}`);

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
          logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] WebSocket connection opened`);
          // Send the ephemeral stream request
          const payload: EphemeralStreamRequest = {
            agent,
            messages,
            client_tools,
          };

          logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Sending initial payload:`, payload);
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
                logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Agent ready:`, readyEvent);

                // Resolve the Promise only when agent is ready
                if (!isResolved) {
                  isResolved = true;
                  resolve(createStreamResult());
                }
                break;

              case 'agent_finished':
                logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Agent finished:`, data);
                handlers.onAgentFinished?.(data as AgentFinishedEvent);
                break;

              case 'agent_error':
                logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Agent error:`, data);
                const errorEvent = data as AgentErrorEvent;
                handlers.onAgentError?.(errorEvent);

                if (!isResolved) {
                  isResolved = true;
                  reject(
                    new EphemeralAgentStreamError(errorEvent.error_message, errorEvent.error_code, errorEvent.details),
                  );
                }
                break;

              case 'message_begin':
                logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Message begin:`, data);
                handlers.onMessage?.(data as MessageEvent);
                handlers.onMessageBegin?.(data as MessageEvent);
                break;

              case 'message_content':
                logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Message content:`, data);
                handlers.onMessage?.(data as MessageEvent);
                handlers.onMessageContent?.(data as MessageEvent);
                break;

              case 'message_end':
                logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Message end:`, data);
                handlers.onMessage?.(data as MessageEvent);
                handlers.onMessageEnd?.(data as MessageEvent);
                break;

              case 'data':
                logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Data:`, data);
                handlers.onData?.(data as DataEvent);
                break;

              case 'request_tool_execution':
                const requestedTool = client_tools?.find((tool) => tool.name === data.tool_name);
                if (requestedTool && requestedTool.callback) {
                  // Calculate the callback input
                  const input_raw = data.input_raw;
                  const callback_input =
                    typeof input_raw === 'object' && input_raw !== null
                      ? input_raw
                      : parse(input_raw, Allow.STR | Allow.OBJ);
                  logger.infoIf(
                    this.verbose,
                    `[EphemeralAgentClient.createStream] Calling callback for tool: ${requestedTool.name} with input:`,
                    callback_input,
                  );
                  // Call the callback with the correct input
                  requestedTool.callback(callback_input);
                  logger.infoIf(
                    this.verbose,
                    `[EphemeralAgentClient.createStream] Callback for tool: ${requestedTool.name} called successfully`,
                  );
                }
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
          logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Connection closed:`, event);
          handlers.onClose?.(event.code, event.reason);

          // Only reject if Promise hasn't been resolved yet
          if (!isResolved) {
            isResolved = true;
            reject(
              new EphemeralAgentStreamError('Connection closed before agent ready', 'CONNECTION_CLOSED', {
                code: event.code,
                reason: event.reason,
              }),
            );
          }
        };

        websocket.onerror = (error) => {
          logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Connection error:`, error);
          if (!isResolved) {
            isResolved = true;
            reject(new EphemeralAgentStreamError('WebSocket connection error', 'CONNECTION_ERROR', { error }));
          }
        };
      } catch (error) {
        logger.infoIf(this.verbose, `[EphemeralAgentClient.createStream] Connection error:`, error);
        if (!isResolved) {
          isResolved = true;
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
  platform_configs: PlatformConfig[];
  agent_id?: string;
  agent_architecture?: AgentArchitecture;
}): UpsertAgentPayload {
  const { name, description, runbook, platform_configs, agent_id, agent_architecture } = options;
  return {
    agent_id: agent_id,
    name,
    description,
    version: '1.0.0',
    runbook,
    agent_architecture: agent_architecture || {
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
      architecture: agent_architecture?.name || ('agent_platform.architectures.default' as const),
      reasoning: 'disabled' as const,
      recursion_limit: 2,
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
export function createUserThreadMessage(text: string, messageId?: string): ThreadMessage {
  return {
    role: 'user',
    content: [{ text, citations: [], kind: 'text' }],
    complete: true,
    message_id: messageId || crypto.randomUUID(),
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
export function createUserThreadMessageWithCitations(
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
    message_id: messageId || crypto.randomUUID(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    agent_metadata: {},
    server_metadata: {},
  };
}

// Legacy aliases for backward compatibility
export const createHumanThreadMessage = createUserThreadMessage;

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

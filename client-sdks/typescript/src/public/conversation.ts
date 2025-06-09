import { parseAgentSSEEvent, streamEventSource } from '../stream';
import { ThreadMessage } from '../private/types';
import { HeadersOptions } from 'openapi-fetch';
import { applyDelta } from '../patch';

const absurd = (_never: never): never => {
  throw new Error('absurd');
};

export interface ConversationMonitor {
  onMessage(message: Partial<ThreadMessage> & { message_id: string }): void;
  onError(error: { errorMessage: string; stackTrace: string }): void;
  onDone(data: { agentId: string; runId: string; threadId: string }): void;
  onStart(data: { agentId: string; runId: string; threadId: string }): void;
}

type MessageId = string;

class Conversation {
  private readonly threadId: string;
  private readonly agentId: string;
  private readonly messages = new Map<MessageId, Partial<ThreadMessage>>();
  private readonly monitor: ConversationMonitor;

  constructor({
    threadId,
    agentId,
    monitor,
  }: {
    threadId: string;
    agentId: string;
    monitor: ConversationMonitor;
  }) {
    this.threadId = threadId;
    this.agentId = agentId;
    this.monitor = monitor;
  }

  public async start({
    baseUrl,
    initialMessage,
    headers,
  }: {
    initialMessage: string;
    baseUrl: string;
    headers?: HeadersOptions;
  }) {
    const url = new URL(
      `/api/public/v2/agents/${this.agentId}/conversations/${this.threadId}/stream`,
      baseUrl
    );
    const stream = streamEventSource({
      method: 'POST',
      url: url.href,
      headers,
      body: JSON.stringify({
        content: initialMessage,
      }),
    });

    await stream.start({
      onEvent: (rawEvent) => {
        const event = parseAgentSSEEvent(rawEvent);
        if (!event) {
          console.error('Error parsing agent event');
          return;
        }

        switch (event.event_type) {
          case 'message_begin': {
            this.messages.set(event.message_id, {});
            this.monitor.onMessage({
              message_id: event.message_id,
            });
            break;
          }
          case 'message_content': {
            const message = this.messages.get(event.message_id);
            if (!message) {
              throw new Error(
                `Cannot find message with id ${event.message_id}`
              );
            }
            const updatedMessage = applyDelta(message, event.delta);
            this.messages.set(event.message_id, updatedMessage);
            this.monitor.onMessage({
              message_id: event.message_id,
              ...updatedMessage,
            });
            break;
          }
          case 'agent_error': {
            this.monitor.onError({
              errorMessage: event.error_message,
              stackTrace: event.error_stack_trace,
            });
            break;
          }
          case 'agent_finished': {
            this.monitor.onDone({
              agentId: event.agent_id,
              runId: event.run_id,
              threadId: event.thread_id,
            });
            break;
          }
          case 'agent_ready': {
            this.monitor.onStart({
              agentId: event.agent_id,
              runId: event.run_id,
              threadId: event.thread_id,
            });
            break;
          }
          case 'message_end': {
            const message = this.messages.get(event.message_id);
            if (!message) {
              throw new Error(
                `Cannot find message with id ${event.message_id}`
              );
            }
            this.messages.set(event.message_id, message);
            this.monitor.onMessage({
              message_id: event.message_id,
              ...message,
            });
            break;
          }
          default:
            absurd(event);
        }
      },
      onError() {},
      onDone() {},
    });
  }
}

export const createStream = ({
  baseUrl,
  headers,
  path,
  monitor,
}: {
  headers?: HeadersOptions;
  baseUrl: string;
  path: string;
  monitor: ConversationMonitor;
}) => ({
  streamConversation: ({
    threadId,
    agentId,
    initialMessage,
  }: {
    threadId: string;
    agentId: string;
    initialMessage: string;
  }) => {
    const conversation = new Conversation({
      threadId,
      agentId,
      monitor,
    });

    conversation.start({
      baseUrl,
      headers,
      initialMessage,
    });
  },
});

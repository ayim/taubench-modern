import { HeadersOptions } from 'openapi-fetch';
import { Delta } from './patch';

export interface RequestUserInput {
  event_type: 'request_user_input';
  timestamp: string;
  message: string;
  timeout: number;
}

export interface AgentReady {
  event_type: 'agent_ready';
  timestamp: string;
  run_id: string;
  thread_id: string;
  agent_id: string;
}

export interface AgentFinished {
  event_type: 'agent_finished';
  timestamp: string;
  run_id: string;
  thread_id: string;
  agent_id: string;
}

export interface AgentError {
  event_type: 'agent_error';
  error_message: string;
  error_stack_trace: string;
  timestamp: string;
  run_id: string;
  thread_id: string;
  agent_id: string;
}

export interface MessageContent {
  event_type: 'message_content';
  delta: Delta;
  sequence_number: number;
  message_id: string;
  timestamp: string;
}

export interface MessageBegin {
  event_type: 'message_begin';
  thread_id: string;
  agent_id: string;
  data: Record<string, object>;
  sequence_number: number;
  message_id: string;
  timestamp: string;
}

export interface MessageEnd {
  event_type: 'message_end';
  thread_id: string;
  agent_id: string;
  data: Record<string, object>;
  sequence_number: number;
  message_id: string;
  timestamp: string;
}

export interface AgentReadySSE {
  event: 'agent_ready';
  data: string;
}

export interface AgentEventSSE {
  event: 'agent_event';
  data: string;
}

export const isAgentSSEEvent = (
  rawEvent: RawEvent
): rawEvent is AgentReadySSE | AgentEventSSE => {
  return ['agent_event', 'agent_ready'].includes(rawEvent.event);
};

export const parseAgentSSEEvent = (rawEvent: RawEvent): AgentEvent | null => {
  try {
    if (!isAgentSSEEvent(rawEvent)) {
      return null;
    }
    return JSON.parse(rawEvent.data) as AgentEvent;
  } catch (unknownError) {
    return null;
  }
};

export type AgentEvent =
  | AgentReady
  | AgentFinished
  | AgentError
  | MessageContent
  | MessageBegin
  | MessageEnd;

export interface RawEvent {
  event: string;
  data: string;
}

export interface StreamMonitor {
  onEvent(event: RawEvent): void;
  onError(error: string): void;
  onDone(): void;
}

export function streamEventSource({
  method,
  url,
  body,
  headers,
}: {
  method: string;
  url: string;
  body: string;
  headers?: HeadersOptions;
}) {
  return {
    async start({ onDone, onError, onEvent }: StreamMonitor) {
      const response = await fetch(url, {
        method,
        headers: {
          ...headers,
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n|\r/g, '\n'); // Normalize line endings

        const parts = buffer.split('\n\n');
        buffer = parts.pop()!; // Incomplete chunk, saved for next loop

        for (const rawChunk of parts) {
          const rawEvent = parseSSEChunk(rawChunk.trim());

          if (!rawEvent) {
            onError(`Cannot parse SSE events: ${rawEvent}`);
            break;
          }
          onEvent(rawEvent);
        }
      }

      onDone();
    },
  };
}

function parseSSEChunk(chunk: string): RawEvent | null {
  const lines = chunk.split('\n');
  let data: string | null = null;
  let event: string | null = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith(':')) {
      continue;
    }

    const [field, ...rest] = trimmed.split(':');
    const value = rest.join(':').trimStart();

    switch (field) {
      case 'event':
        event = value;
        break;
      case 'data':
        data = data ? data + '\n' + value : value;
        break;
    }
  }

  if (event === null || data === null) {
    return null;
  }

  return {
    event,
    data,
  };
}

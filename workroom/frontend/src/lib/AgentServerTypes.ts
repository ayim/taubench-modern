// TODO: integrate _new_ (from agent-platform) agent-server-interface when
// we figure out how to get some of the types that represent data coming over
// the websocket auto-generated as part of the openapi spec. For now, this is
// a minimal set of important new types that the frontend needs. In follow-on
// work we'll shoot to migrate both types.ts to new ASI types.

// -----------------------------------------------------------------------------
// Streaming Contract
// -----------------------------------------------------------------------------

export type AgentErrorStreamPayload = {
  code: string;
  error_id: string;
  message: string;
  data?: Record<string, unknown>;
};

// Taken from: https://github.com/Sema4AI/agent-platform/blob/588d14f3f945990329233d66007748ec5101753f/core/src/agent_platform/core/delta/base.py
export interface GenericDelta {
  op: 'add' | 'remove' | 'replace' | 'move' | 'copy' | 'test' | 'concat_string' | 'inc';
  path: string;
  value?: string | number | boolean | object;
  from_?: string;
}

// Taken from: https://github.com/Sema4AI/agent-platform/blob/588d14f3f945990329233d66007748ec5101753f/core/src/agent_platform/core/streaming/delta.py

export type StreamingDeltaType =
  | 'agent_ready'
  | 'agent_finished'
  | 'agent_error'
  | 'message_content'
  | 'message_metadata'
  | 'message_begin'
  | 'message_end'
  | 'request_user_input'
  | 'thread_name_updated';

export interface StreamingDeltaBase {
  timestamp: string;
  event_type: StreamingDeltaType;
}

export interface StreamingDeltaRequestUserInput extends StreamingDeltaBase {
  event_type: 'request_user_input';
  message: string;
  timeout: number;
}

export interface StreamingDeltaAgentBase extends StreamingDeltaBase {
  run_id: string;
  thread_id: string;
  agent_id: string;
}

export interface StreamingDeltaAgentReady extends StreamingDeltaAgentBase {
  event_type: 'agent_ready';
}

export interface StreamingDeltaAgentFinished extends StreamingDeltaAgentBase {
  event_type: 'agent_finished';
}

export interface StreamingDeltaAgentError extends StreamingDeltaAgentBase {
  event_type: 'agent_error';
  error: AgentErrorStreamPayload;
}

export interface StreamingDeltaMessageBase extends StreamingDeltaBase {
  sequence_number: number;
  message_id: string;
}

export interface StreamingDeltaMessageContent extends StreamingDeltaMessageBase {
  event_type: 'message_content';
  delta: GenericDelta;
}

export interface StreamingDeltaMessageBegin extends StreamingDeltaMessageBase {
  event_type: 'message_begin';
  thread_id: string;
  agent_id: string;
  data: Record<string, object>;
}

export interface StreamingDeltaMessageEnd extends StreamingDeltaMessageBase {
  event_type: 'message_end';
  thread_id: string;
  agent_id: string;
  data: Record<string, object>;
}

// Below are created based on inheritance of dataclasses in...
// https://github.com/Sema4AI/agent-platform/blob/588d14f3f945990329233d66007748ec5101753f/core/src/agent_platform/core/streaming/delta.py

export type StreamingDeltaMessage =
  | StreamingDeltaMessageContent
  | StreamingDeltaMessageBegin
  | StreamingDeltaMessageEnd;

export interface StreamingDeltaThreadNameUpdated extends StreamingDeltaBase {
  event_type: 'thread_name_updated';
  thread_id: string;
  agent_id: string;
  new_name: string;
  old_name?: string | null;
  reason: 'auto' | 'manual';
}

export type StreamingDeltaAgent = StreamingDeltaAgentReady | StreamingDeltaAgentFinished | StreamingDeltaAgentError;

export type StreamingDelta =
  | StreamingDeltaRequestUserInput
  | StreamingDeltaAgent
  | StreamingDeltaMessage
  | StreamingDeltaThreadNameUpdated;

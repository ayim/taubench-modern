import { useEffect, useState } from 'react';
import { ThreadMessage, ThreadContent, ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { findByPointer } from '@jsonjoy.com/json-pointer';
import { applyPatch, Operation } from 'json-joy/esm/json-patch/index.js';
import { v4 as uuidv4 } from 'uuid';
import { QueryClient, useQueryClient } from '@tanstack/react-query';

import { AgentErrorStreamPayload, StreamingDelta, StreamingDeltaMessageContent } from '../lib/AgentServerTypes';
import { SparAPIClient } from '../api';
import { useSparUIContext } from '../api/context';
import { threadMessagesQueryKey, useThreadFilesRefetch, useUploadThreadFilesMutation } from '../queries/threads';

type MessageListener = (
  messages: ThreadMessage[] | undefined,
  streamError: AgentErrorStreamPayload | undefined,
) => void;

class StreamManager {
  private wsMap: Record<string, WebSocket | null> = {};

  private messagesMap: Record<string, ThreadMessage[]> = {};

  private streamErrorMap: Record<string, AgentErrorStreamPayload | undefined> = {};

  private messageListeners: Map<string, Set<MessageListener>> = new Map();

  private queryClient: QueryClient | undefined;

  public async initiateStream({
    sparAPIClient,
    queryClient,
    content,
    threadId,
    agentId,
  }: {
    sparAPIClient: SparAPIClient;
    queryClient: QueryClient;
    content: ThreadContent[];
    threadId: string;
    agentId: string;
  }) {
    this.streamErrorMap[threadId] = undefined;
    this.queryClient = queryClient;

    this.messagesMap[threadId] = [];
    this.messagesMap[threadId].push({
      message_id: uuidv4(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      agent_metadata: {},
      server_metadata: {},
      commited: true,
      complete: true,
    });

    this.emitMessage(threadId);

    const ws = await sparAPIClient.startWebsocketStream(agentId);

    /**
     * Wait for the WebSocket to be open before resolving
     * - initiating stream and sending additional messages will otherwise fail
     */
    await new Promise<void>((resolve) => {
      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            thread_id: threadId,
            agent_id: agentId,
            messages: [
              {
                role: 'user',
                content,
              },
            ],
          }),
        );
        resolve();
      };
    });

    ws.onmessage = (event) => {
      let streamingDelta: StreamingDelta | null = null;

      try {
        streamingDelta = JSON.parse(event.data) as StreamingDelta;
      } catch (error) {
        return;
      }

      if (!streamingDelta) return;

      switch (streamingDelta.event_type) {
        case 'message_begin': {
          this.messagesMap[threadId].push({ message_id: streamingDelta.message_id } as ThreadMessage);
          break;
        }
        case 'message_content': {
          this.messageStream(threadId, streamingDelta);
          break;
        }
        case 'message_end': {
          this.messageEnd(threadId);
          break;
        }
        case 'agent_error': {
          this.streamErrorMap[threadId] = streamingDelta.error;
          this.messageEnd(threadId);
          break;
        }
        default:
      }
    };

    this.wsMap[threadId] = ws;
  }

  /**
   * Send a client tool result to the websocket
   */
  public async sendClientToolResult({
    threadId,
    sparAPIClient,
    queryClient,
    agentId,
    tool,
    result,
    error: clientToolError,
  }: {
    sparAPIClient: SparAPIClient;
    queryClient: QueryClient;
    agentId: string;
    threadId: string;
    tool: ThreadToolUsageContent;
    result: string;
    error?: string;
  }) {
    let activeWebSocketForThread = this.wsMap[threadId];
    if (!activeWebSocketForThread || activeWebSocketForThread.readyState !== WebSocket.OPEN) {
      // Use initiateStream to set up the WebSocket connection with empty messages
      await this.initiateStream({
        sparAPIClient,
        queryClient,
        content: [],
        threadId,
        agentId,
      });
      activeWebSocketForThread = this.wsMap[threadId];
    }

    if (!activeWebSocketForThread) {
      throw new Error('No active WebSocket connection for this thread');
    }

    // Create the tool result message following the Python pattern
    const toolResultMessage = {
      event_type: 'client_tool_result',
      tool_call_id: tool.tool_call_id,
      result: {
        output: result,
        error: clientToolError ?? '',
      },
    };

    // Send the tool result directly via the existing WebSocket
    try {
      activeWebSocketForThread.send(JSON.stringify(toolResultMessage));
    } catch (unexpectedToolError) {
      throw new Error(`Failed to send tool result: ${unexpectedToolError}`);
    }
  }

  public getCurrentMessages(threadId: string) {
    return this.messagesMap[threadId];
  }

  public addMessageListener(threadId: string, listener: MessageListener): void {
    if (!this.messageListeners.has(threadId)) {
      this.messageListeners.set(threadId, new Set());
    }

    this.messageListeners.get(threadId)!.add(listener);

    this.emitMessage(threadId);
  }

  public removeMessageListener(threadId: string, listener: MessageListener): void {
    const listenersSet = this.messageListeners.get(threadId);
    if (listenersSet) {
      listenersSet.delete(listener);
      if (listenersSet.size === 0) {
        this.messageListeners.delete(threadId);
      }
    }
  }

  private emitMessage(threadId: string): void {
    const listenersSet = this.messageListeners.get(threadId);
    if (listenersSet) {
      const messages = this.messagesMap[threadId];
      listenersSet.forEach((listener) =>
        listener(messages && messages.length > 0 ? [...messages] : undefined, this.streamErrorMap[threadId]),
      );
    }
  }

  /**
   * Merge the streaming delta into the chunks map
   * @param threadId - threadId
   * @param streamingDelta - streaming delta
   */
  private messageStream(threadId: string, streamingDelta: StreamingDeltaMessageContent) {
    // For this messageId, websocket has sent updates
    const messageId = streamingDelta.message_id;

    const threadChunks = this.messagesMap[threadId];
    // Chunk index according to messageId for which updates are received
    const chunkIndex = threadChunks.findIndex((chunk) => chunk.message_id === messageId);

    // below scenario should never happen
    if (chunkIndex === -1) throw new Error('Chunk not found');

    let { delta } = streamingDelta;
    // If this is a concat operation, transform it into a "replace" with the concatenated value
    if (delta.op === 'concat_string') {
      const { val: oldValue } = findByPointer(delta.path, threadChunks[chunkIndex]);

      // concatinated value
      const concatinatedVal = (oldValue ?? '') + (delta.value as string);
      delta = {
        op: 'replace',
        path: delta.path, // keep the same path
        value: concatinatedVal,
      };
    }

    const patchedResult = applyPatch(threadChunks[chunkIndex], [delta as Operation], { mutate: false })
      .doc as ThreadMessage;

    threadChunks[chunkIndex] = patchedResult;

    this.emitMessage(threadId);
  }

  private messageEnd(threadId: string) {
    const threadMessages = this.messagesMap[threadId] ?? [];

    /**
     * Agent messages (like tool call updates) can live between multiple message_end events.
     * Removing these "incomplete" messages will cause current UI chat stream to lose these updates until refetch is made.
     */
    const { completedMessages, incompleteMessages } = threadMessages.reduce<{
      completedMessages: ThreadMessage[];
      incompleteMessages: ThreadMessage[];
    }>(
      (acc, message) => {
        if (message.complete) {
          acc.completedMessages.push(message);
          return acc;
        }
        acc.incompleteMessages.push(message);
        return acc;
      },
      { completedMessages: [], incompleteMessages: [] },
    );

    if (completedMessages.length > 0) {
      this.queryClient?.setQueryData(threadMessagesQueryKey(threadId), (messages: ThreadMessage[]) => {
        return [...messages, ...completedMessages];
      });
    }

    this.messagesMap[threadId] = incompleteMessages;
    this.emitMessage(threadId);
  }
}

export const streamManager = new StreamManager();

export const useMessageStream = ({ agentId, threadId }: { agentId: string; threadId: string }) => {
  const { sparAPIClient } = useSparUIContext();
  const queryClient = useQueryClient();
  const { mutateAsync: uploadFiles, isPending: uploadingFiles } = useUploadThreadFilesMutation({ threadId });
  const refetchFiles = useThreadFilesRefetch({ threadId });

  const [streamingMessages, setStreamingMessages] = useState<ThreadMessage[] | undefined>(undefined);
  const [streamError, setStreamError] = useState<AgentErrorStreamPayload | undefined>(undefined);

  const isStreaming = streamingMessages?.some((message) => message.role === 'agent' && !message.complete) ?? false;

  const sendMessage = async (text: string, files: File[]) => {
    const uploadedAttachments = files.length ? await uploadFiles({ files }) : [];
    if (files.length) {
      // only refetch files if any file is uploaded
      await refetchFiles();
    }
    const content: ThreadContent[] = [...uploadedAttachments];
    if (text.trim()) {
      // only add text message if it is not empty
      content.push({ kind: 'text', text, complete: true });
    }
    await streamManager.initiateStream({ sparAPIClient, queryClient, content, threadId, agentId });
  };

  const sendClientToolMessage = async (tool: ThreadToolUsageContent, result: string, error?: string) => {
    await streamManager.sendClientToolResult({ threadId, tool, result, error, sparAPIClient, queryClient, agentId });
  };

  useEffect(() => {
    const messageListener: MessageListener = (messages, err) => {
      if (messages && messages[messages.length - 1].complete) {
        messages.push({
          message_id: uuidv4(),
          role: 'agent',
          content: [
            {
              kind: 'thought',
              thought: '',
              complete: false,
            },
          ],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          complete: false,
          commited: false,
        });
      }
      setStreamingMessages(messages);
      setStreamError(err);
    };

    streamManager.addMessageListener(threadId, messageListener);

    return () => {
      streamManager.removeMessageListener(threadId, messageListener);
    };
  }, [agentId, threadId]);

  return {
    sendMessage,
    streamingMessages,
    uploadingFiles,
    streamError,
    sendClientToolMessage,
    isStreaming,
  };
};

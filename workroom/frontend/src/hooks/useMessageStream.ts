import { useEffect, useState } from 'react';
import {
  ThreadMessage,
  ThreadContent,
  ThreadToolUsageContent,
  Thread,
  ThreadFormattedTextContent,
  ThreadTextContent,
} from '@sema4ai/agent-server-interface';
import { findByPointer } from '@jsonjoy.com/json-pointer';
import { applyPatch, Operation } from 'json-joy/esm/json-patch/index.js';
import { v4 as uuidv4 } from 'uuid';
import { QueryClient, useQueryClient } from '@tanstack/react-query';

import {
  threadMessagesQueryKey,
  threadQueryKey,
  threadsQueryKey,
  useThreadFilesRefetch,
  useUploadThreadFilesMutation,
} from '~/queries/threads';
import {
  AgentErrorStreamPayload,
  StreamingDelta,
  StreamingDeltaMessageContent,
  StreamingDeltaMessageEnd,
  StreamingDeltaThreadNameUpdated,
} from '../lib/AgentServerTypes';
import { AgentAPIClient } from '../lib/AgentAPIClient';
import { useSparUIContext } from '../api/context';

type MessageListener = (
  messages: ThreadMessage[] | undefined,
  streamError: AgentErrorStreamPayload | undefined,
) => void;

const mergeMessagesToCache = ({
  cachedMessages,
  newMessages,
}: {
  cachedMessages: ThreadMessage[];
  newMessages: ThreadMessage[];
}): ThreadMessage[] => {
  const newMessageIds = new Set(newMessages.map((message) => message.message_id));
  const updatedCachedMessages = cachedMessages.map((cached) => {
    if (newMessageIds.has(cached.message_id)) {
      return newMessages.find((message) => message.message_id === cached.message_id) ?? cached;
    }
    return cached;
  });
  const messagesToAdd = newMessages.filter(
    (curr) => !cachedMessages.some((cached) => cached.message_id === curr.message_id),
  );
  return [...updatedCachedMessages, ...messagesToAdd];
};

class StreamManager {
  private wsMap: Record<string, WebSocket | null> = {};

  private messagesMap: Record<string, ThreadMessage[]> = {};

  private streamErrorMap: Record<string, AgentErrorStreamPayload | undefined> = {};

  private messageListeners: Map<string, Set<MessageListener>> = new Map();

  private queryClient: QueryClient | undefined;

  public async initiateStream({
    startWebsocketStream,
    queryClient,
    content,
    threadId,
    agentId,
  }: {
    startWebsocketStream: (agentId: string) => Promise<WebSocket>;
    queryClient: QueryClient;
    content: ThreadContent[];
    threadId: string;
    agentId: string;
  }) {
    this.streamErrorMap[threadId] = undefined;
    this.queryClient = queryClient;

    this.messagesMap[threadId] = [];

    const userMessage = {
      message_id: uuidv4(),
      content,
      role: 'user',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      agent_metadata: {},
      server_metadata: {},
      commited: true,
      complete: true,
    } satisfies ThreadMessage;

    this.messagesMap[threadId].push(userMessage);

    this.emitMessage(threadId);
    const ws = await startWebsocketStream(agentId);

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
            messages: [userMessage],
          }),
        );
        resolve();
      };
    });

    ws.onmessage = (event) => {
      let streamingDelta: StreamingDelta | null = null;

      try {
        streamingDelta = JSON.parse(event.data) as StreamingDelta;
      } catch {
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
          this.messageEnd(threadId, streamingDelta);
          break;
        }
        case 'agent_error': {
          this.streamErrorMap[threadId] = streamingDelta.error;
          this.messageEnd(threadId);
          break;
        }
        case 'thread_name_updated': {
          this.threadNameUpdated(streamingDelta);
          break;
        }
        default:
      }
    };

    this.wsMap[threadId] = ws;
  }

  private threadNameUpdated(streamingDelta: StreamingDeltaThreadNameUpdated) {
    const { thread_id: threadId, agent_id: agentId, new_name: newName } = streamingDelta;

    const updateThreadName = (thread: Thread | undefined) => {
      if (!thread || thread.thread_id !== threadId || thread.name === newName) {
        return thread;
      }
      return { ...thread, name: newName };
    };

    this.queryClient?.setQueryData(threadQueryKey(threadId), (thread: Thread | undefined) => {
      return updateThreadName(thread);
    });

    this.queryClient?.setQueryData(threadsQueryKey(agentId), (threads: Thread[] | undefined) => {
      if (!threads) {
        return threads;
      }
      return threads.map(updateThreadName);
    });
  }

  /**
   * Send a client tool result to the websocket
   */
  public async sendClientToolResult({
    threadId,
    agentAPIClient,
    queryClient,
    agentId,
    tool,
    result,
    error: clientToolError,
  }: {
    agentAPIClient: AgentAPIClient;
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
        startWebsocketStream: agentAPIClient.startWebsocketStream,
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

  /**
   * Stop the stream for a given thread
   * - Closes the WebSocket connection
   * - Saves only completed messages (discards incomplete ones)
   * - Updates the query cache with completed messages
   *
   * Note: This mirrors server behavior - when a WebSocket disconnects,
   * the server cancels tasks and does NOT persist uncommitted messages.
   * Only messages that were explicitly committed before disconnect are saved.
   */
  public stopStream(threadId: string): void {
    const ws = this.wsMap[threadId];

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
    }

    this.wsMap[threadId] = null;

    const threadMessages = this.messagesMap[threadId] ?? [];
    const completedMessages = threadMessages.filter((message) => message.complete);

    if (completedMessages.length > 0) {
      this.queryClient?.setQueryData(threadMessagesQueryKey(threadId), (cachedMessages: ThreadMessage[] = []) =>
        mergeMessagesToCache({ cachedMessages, newMessages: completedMessages }),
      );
    }

    this.messagesMap[threadId] = [];
    this.streamErrorMap[threadId] = undefined;

    this.emitMessage(threadId);
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
      const messages = this.messagesMap[threadId] || [];

      listenersSet.forEach((listener) =>
        listener(messages.length > 0 ? [...messages] : undefined, this.streamErrorMap[threadId]),
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

  private messageEnd(threadId: string, messageEndDelta?: StreamingDeltaMessageEnd): void {
    const threadMessages = this.messagesMap[threadId] ?? [];

    // Replace streamed message with server's committed version (includes metadata, timestamps, etc.)
    // Without this logic, "created_at" is set in 1970
    if (messageEndDelta) {
      const messageIndex = threadMessages.findIndex((message) => message.message_id === messageEndDelta.message_id);
      if (messageIndex !== -1) {
        threadMessages[messageIndex] = messageEndDelta.data as unknown as ThreadMessage;
      }
    }

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
      this.queryClient?.setQueryData(threadMessagesQueryKey(threadId), (cachedMessages: ThreadMessage[] = []) =>
        mergeMessagesToCache({ cachedMessages, newMessages: completedMessages }),
      );
    }

    this.messagesMap[threadId] = incompleteMessages;
    this.emitMessage(threadId);
  }
}

export const streamManager = new StreamManager();

export const useMessageStream = ({ agentId, threadId }: { agentId: string; threadId: string }) => {
  const { agentAPIClient } = useSparUIContext();
  const queryClient = useQueryClient();
  const { mutateAsync: uploadFiles, isPending: uploadingFiles } = useUploadThreadFilesMutation({ threadId });
  const refetchFiles = useThreadFilesRefetch({ threadId, agentId });

  const [streamingMessages, setStreamingMessages] = useState<ThreadMessage[] | undefined>(undefined);
  const [streamError, setStreamError] = useState<AgentErrorStreamPayload | undefined>(undefined);

  const isStreaming = streamingMessages?.some((message) => message.role === 'agent' && !message.complete) ?? false;

  const sendMessage = async (
    { text, type = 'text' }: { text: string; type?: 'text' | 'formatted-text' },
    files: File[],
  ): Promise<{ success: true; data: null } | { success: false; error: { message: string } }> => {
    const hasText = text.trim().length > 0;
    const hasAttachments = files.length > 0;

    if (!hasText && !hasAttachments) {
      return {
        success: false,
        error: {
          message: 'Sending empty messages is not supported',
        },
      };
    }

    const uploadedAttachments = await (async (): Promise<
      | { success: true; data: Awaited<ReturnType<typeof uploadFiles>> }
      | {
          success: false;
          error: {
            message: string;
          };
        }
    > => {
      if (!hasAttachments) {
        return {
          success: true,
          data: [],
        };
      }

      try {
        const uploadedFiles = await uploadFiles({ files });

        await refetchFiles();

        return {
          success: true,
          data: uploadedFiles,
        };
      } catch (e) {
        const error = e as Error;
        return {
          success: false,
          error: {
            message: error.message,
          },
        };
      }
    })();

    if (!uploadedAttachments.success) {
      return uploadedAttachments;
    }

    const content: ThreadContent[] = [...uploadedAttachments.data];

    if (hasText) {
      const base = { text, complete: true, content_id: uuidv4() };

      // ThreadContent is a discriminated union: kind must be a concrete literal, not `'text' | 'formatted-text'`.
      if (type === 'formatted-text') {
        content.push({ kind: 'formatted-text', ...base } satisfies ThreadFormattedTextContent);
      } else {
        content.push({ kind: 'text', ...base } satisfies ThreadTextContent);
      }
    }

    try {
      await streamManager.initiateStream({
        startWebsocketStream: agentAPIClient.startWebsocketStream,
        queryClient,
        content,
        threadId,
        agentId,
      });

      return {
        success: true,
        data: null,
      };
    } catch {
      return {
        success: false,
        error: {
          message: 'Failed to reach the agent: if the issue persists, please file a support ticket',
        },
      };
    }
  };

  const sendClientToolMessage = async (tool: ThreadToolUsageContent, result: string, error?: string) => {
    await streamManager.sendClientToolResult({ threadId, tool, result, error, agentAPIClient, queryClient, agentId });
  };

  const stopStream = () => {
    streamManager.stopStream(threadId);
  };

  useEffect(() => {
    const messageListener: MessageListener = (messages, err) => {
      if (messages && messages[messages.length - 1].complete) {
        messages.push({
          message_id: uuidv4(),
          role: 'agent',
          content: [],
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
    stopStream,
  };
};

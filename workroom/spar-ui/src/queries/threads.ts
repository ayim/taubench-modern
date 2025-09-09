import { Thread, ThreadAttachmentContent, ThreadMessage } from '@sema4ai/agent-server-interface';

import { createSparMutation, createSparQueryOptions, createSparQuery } from './shared';
import { getFileSize } from '../common/helpers';

/**
 * List Threads
 */
export const threadsQueryKey = (agentId: string) => ['threads', agentId];

export const threadsQueryOptions = createSparQueryOptions<{ agentId: string }>()(({ sparAPIClient, agentId }) => ({
  queryKey: threadsQueryKey(agentId),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/', {
      params: { query: { aid: agentId } },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to fetch threads');
    }

    return response.data;
  },
}));

export const useThreadsQuery = createSparQuery(threadsQueryOptions);

/**
 * Get Thread
 */
export const threadQueryKey = (threadId: string) => ['thread', threadId];

export const threadQueryOptions = createSparQueryOptions<{ threadId: string }>()(({ sparAPIClient, threadId }) => ({
  queryKey: threadQueryKey(threadId),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/{tid}', {
      params: { path: { tid: threadId } },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to fetch threads');
    }

    return response.data;
  },
}));

export const useThreadQuery = createSparQuery(threadQueryOptions);

/**
 * Get Thread messages
 */
export const threadMessagesQueryKey = (threadId: string) => ['thread', threadId, 'messages'];

export const threadMessagesQueryOptions = createSparQueryOptions<{ threadId: string }>()(
  ({ sparAPIClient, threadId }) => ({
    queryKey: threadMessagesQueryKey(threadId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/{tid}/state', {
        params: { path: { tid: threadId } },
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to fetch thread messages');
      }

      // TODO-V2: Why is "ThreadMessage = Overwrite<components['schemas']['ThreadMessage']>{...}" happening at @sema4ai/agent-server-interface
      return (response.data.messages as ThreadMessage[]) || [];
    },
  }),
);

export const useThreadMessagesQuery = createSparQuery(threadMessagesQueryOptions);

/**
 * Create Thread
 */
export const useCreateThreadMutation = createSparMutation<
  { agentId: string },
  { name: string; startingMessage: string }
>()(({ agentId, sparAPIClient }) => ({
  mutationFn: async ({ name, startingMessage }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/threads/', {
      body: {
        name,
        agent_id: agentId,
        messages: [
          {
            role: 'agent',
            content: [{ kind: 'text', text: startingMessage, complete: true }],
            complete: true,
            commited: false,
          },
        ],
      },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to create thread');
    }

    return response.data;
  },
}));

/**
 * Update Thread
 */
export const useUpdateThreadMutation = createSparMutation<{ agentId: string }, { threadId: string; name: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ threadId, name }: { threadId: string; name: string }) => {
      const response = await sparAPIClient.queryAgentServer('patch', '/api/v2/threads/{tid}', {
        params: { path: { tid: threadId } },
        body: { name },
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to update thread');
      }

      return response.data;
    },
    onSuccess: (_, { threadId, name }, { agentId }) => {
      queryClient.setQueryData(threadsQueryKey(agentId), (threads: Thread[]) => {
        return !threads ? [] : threads.map((thread) => (thread.thread_id === threadId ? { ...thread, name } : thread));
      });
    },
  }),
);

/**
 * Delete Thread
 */
export const useDeleteThreadMutation = createSparMutation<{ agentId: string }, { threadId: string }>()(
  ({ sparAPIClient, queryClient, agentId }) => ({
    mutationFn: async ({ threadId }) => {
      const response = await sparAPIClient.queryAgentServer('delete', '/api/v2/threads/{tid}', {
        params: { path: { tid: threadId } },
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to delete thread');
      }

      return response.data;
    },

    onSuccess: (_, { threadId }) => {
      // agentId is available from the hook params
      queryClient.setQueryData(threadsQueryKey(agentId), (threads: Thread[]) => {
        return !threads ? [] : threads.filter((thread) => thread.thread_id !== threadId);
      });
    },
  }),
);

/**
 * Upload Thread Files
 */
export const useUploadThreadFilesMutation = createSparMutation<{ threadId: string }, { files: File[] }>()(
  ({ sparAPIClient, threadId }) => ({
    mutationFn: async ({ files }) => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/threads/{tid}/files', {
        body: { files: files as unknown as string[] },
        params: { path: { tid: threadId } },
        bodySerializer(body) {
          return body.files.reduce((formData, file) => {
            formData.append('files', file);
            return formData;
          }, new FormData());
        },
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to upload thread files');
      }

      const attachements = response.data.map(
        (file) =>
          ({
            kind: 'attachment' as const,
            name: file.file_ref,
            uri: `agent-server-file://${file.file_id}`,
            mime_type: file.mime_type,
            description: getFileSize(file.file_size_raw),
            base64_data: null,
            complete: true,
          }) satisfies ThreadAttachmentContent,
      );

      return attachements;
    },
  }),
);

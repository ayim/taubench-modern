import {
  paths as AgentServerPaths,
  Thread,
  ThreadAttachmentContent,
  ThreadMessage,
} from '@sema4ai/agent-server-interface';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import { getFileSize } from '../common/helpers';
import { createSparMutation, createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';
import { streamManager } from '../hooks/useMessageStream';

/**
 * List Threads
 */
export const threadsQueryKey = (agentId: string) => ['threads', agentId];

export const threadsQueryOptions = createSparQueryOptions<{ agentId: string; limit?: number }>()(
  ({ sparAPIClient, agentId, limit }) => ({
    queryKey: threadsQueryKey(agentId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/', {
        params: { query: { aid: agentId, limit } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch threads', {
          code: response.code,
          resource: ResourceType.Thread,
        });
      }

      return response.data;
    },
  }),
);

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
      throw new QueryError(response.message || 'Failed to fetch threads', {
        code: response.code,
        resource: ResourceType.Thread,
      });
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
        throw new QueryError(response.message || 'Failed to fetch thread messages', {
          code: response.code,
          resource: ResourceType.Thread,
        });
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
  { name: string; startingMessage: string; isUserMessage?: boolean }
>()(({ agentId, sparAPIClient, queryClient }) => ({
  mutationFn: async ({ name, startingMessage, isUserMessage = true }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/threads/', {
      body: {
        name,
        agent_id: agentId,
        ...(isUserMessage
          ? {}
          : {
              messages: [
                {
                  role: 'agent',
                  content: [{ kind: 'text', text: startingMessage, complete: true }],
                  complete: true,
                  commited: false,
                },
              ],
            }),
      },
    });
    if (!response.success) {
      throw new QueryError(response.message || 'Failed to create thread', {
        code: response.code,
        resource: ResourceType.Thread,
      });
    }

    if (!response.data.thread_id) {
      throw new QueryError('Failed to create thread', { code: 'bad_request', resource: ResourceType.Thread });
    }

    if (isUserMessage) {
      streamManager.initiateStream({
        content: [{ kind: 'text', text: startingMessage, complete: true }],
        agentId,
        queryClient,
        threadId: response.data.thread_id,
        startWebsocketStream: sparAPIClient.startWebsocketStream,
      });
    }

    return response.data;
  },
  onSuccess: (newThreadData) => {
    queryClient.setQueryData(threadsQueryKey(agentId), (threads: Thread[]) => {
      return [newThreadData, ...(threads || [])];
    });
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
        throw new QueryError(response.message || 'Failed to update thread', {
          code: response.code,
          resource: ResourceType.Thread,
        });
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
        throw new QueryError(response.message || 'Failed to delete thread', {
          code: response.code,
          resource: ResourceType.Thread,
        });
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
        // The current error returned by the agent-server is not customer facing at all
        throw new QueryError('Failed to upload the file(s)', { code: 'bad_request', resource: ResourceType.Thread });
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

export const threadFilesQueryKey = (threadId: string) => ['thread', threadId, 'files'];

export type ThreadFiles =
  AgentServerPaths['/api/v2/threads/{tid}/files']['get']['responses'][200]['content']['application/json'];
export const threadFilesQueryOptions = createSparQueryOptions<{ threadId: string }>()(
  ({ sparAPIClient, threadId }) => ({
    queryKey: threadFilesQueryKey(threadId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/{tid}/files', {
        params: { path: { tid: threadId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch threads', {
          code: response.code,
          resource: ResourceType.Thread,
        });
      }

      return response.data;
    },
  }),
);

/**
 * Get Thread Files
 */
export const useThreadFilesQuery = createSparQuery(threadFilesQueryOptions);

export const useThreadFilesRefetch = ({ threadId }: { threadId: string }) => {
  const queryClient = useQueryClient();

  return useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: threadFilesQueryKey(threadId) });
  }, [queryClient, threadId]);
};

/**
 * Download Thread File
 */
type DownloadThreadFileMutationResult<TType extends 'download' | 'inline'> = TType extends 'inline'
  ? { file: File }
  : void;

export const useDownloadThreadFileMutation = <TType extends 'download' | 'inline'>(params: { type: TType }) =>
  createSparMutation<Record<string, never>, { threadId: string; name: string }>()(({ sparAPIClient }) => ({
    mutationFn: async ({ threadId, name }): Promise<DownloadThreadFileMutationResult<TType>> => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/threads/{tid}/files/download/', {
        params: { path: { tid: threadId }, query: { file_ref: name } },
        parseAs: 'stream',
      });

      if (!response.success) {
        // This is a best guess scenario here: the agent server returns "unexpected error" here
        throw new QueryError('Failed to download file: the file cannot be found', {
          code: 'unexpected',
          resource: ResourceType.ThreadFile,
        });
      }

      const reader = (response.data as ReadableStream)?.getReader();
      if (!reader) {
        throw new QueryError(
          'Something went wrong when downloading the file. If the issue persists, reach out to our support.',
          { code: 'unexpected', resource: ResourceType.ThreadFile },
        );
      }

      const chunks: BlobPart[] = [];
      let done = false;

      while (!done) {
        // eslint-disable-next-line no-await-in-loop
        const { value, done: streamDone } = await reader.read();
        if (value) chunks.push(value);
        done = streamDone;
      }

      const blob = new Blob(chunks);

      if (params.type === 'inline') {
        const file = new File([blob], name);
        return { file } as DownloadThreadFileMutationResult<TType>;
      }

      const downloadFileAndCleanUp = () => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');

        a.href = url;
        a.download = name;

        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
      };

      downloadFileAndCleanUp();

      return undefined as DownloadThreadFileMutationResult<TType>;
    },
  }))({});

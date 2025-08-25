import { ApiClient } from '@sema4ai/agent-components';
import { Agent, Thread } from '~/types';
import { errorToast, successToast, warnToast } from '~/utils/toasts';
import { AgentAPIClient } from '../AgentAPIClient';
import { getDocumentAPIClient } from '../DocumentAPIClient';

export const getChatAPIClient = (
  tenantId: string,
  agentAPIClient: AgentAPIClient,
  options?: {
    isDeveloperModeEnabled?: boolean;
    isFeedbackEnabled?: boolean;
    isAgentDetailsEnabled?: boolean;
  },
): ApiClient => {
  const { getDocumentTypesList, getFile } = getDocumentAPIClient(tenantId, agentAPIClient);

  // v2 integration, remove this downloadFile type once agent-components is updated
  const apiClient: ApiClient & { downloadFile: unknown } = {
    getDocumentTypesList,
    getFile,
    getDocumentDetails: async (documentTypeName, documentId) => {
      return agentAPIClient.docIntelliFetch(
        tenantId,
        'get',
        '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/paginated-document-workitems/{documentId}',
        { params: { path: { documentId, documentTypeName, workspaceId: tenantId } } },
      );
    },
    getChatList: async (queryOptions) => {
      const data = (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/', {
        params: { query: queryOptions },
        errorMsg: 'Failed to fetch threads',
      })) as Thread[]; // TODO: Remove type casting once ASI is fixed

      // Backwards compatibillity for Agent Backend < 1.2.1
      if (queryOptions?.aid) {
        return data.filter((curr) => curr.agent_id === queryOptions.aid);
      }

      return data;
    },
    getChat: async (tid) => {
      return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}', {
        params: { path: { tid } },
        errorMsg: 'Failed to fetch thread',
        toastMessage: 'Thread not found',
      })) as Thread; // TODO: Remove type casting once ASI is fixed
    },
    createChat: async (agent_id, name, starting_message) => {
      return (await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/threads/', {
        body: { name, agent_id, starting_message: starting_message ?? undefined },
        errorMsg: 'Failed to create thread',
      })) as Thread; // TODO: Remove type casting once ASI is fixed
    },
    updateChat: async (agent_id, thread_id, name) => {
      return agentAPIClient.agentFetch(tenantId, 'patch', '/api/v2/threads/{tid}', {
        params: { path: { tid: thread_id } },
        body: { agent_id, name },
        errorMsg: 'Failed to update thread',
      }) as Promise<Thread>;
    },
    deleteChat: async (tid) => {
      await agentAPIClient.agentFetch(tenantId, 'delete', '/api/v2/threads/{tid}', {
        params: { path: { tid } },
        errorMsg: 'Failed to delete thread',
      });
    },
    getChatState: async (tid) => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}/state', {
        params: { path: { tid } },
        errorMsg: 'Failed to fetch thread state',
        silent: true,
      });
      return response as Thread; // TODO: Remove type casting once ASI is fixed
    },
    // TODO: cleanup different event handlers
    startWebsocketStream: async ({ agentId, onclose, onerror, onmessage, userInput }) => {
      const { url, token, withBearerTokenAuth } = await agentAPIClient.getWsStreamUrl({ agentId, tenantId });
      return new Promise((resolve, reject) => {
        const ws = withBearerTokenAuth ? new WebSocket(url, ['Bearer', token]) : new WebSocket(url);

        ws.onopen = () => {
          // console.log('[WEBSOCKET] onopen', {
          //   thread_id: threadId,
          //   agent_id: agentId,
          // });
          // Resolve the promise with the websocket when it's open
          ws.send(userInput);
          resolve(ws);
        };

        ws.onmessage = (event) => {
          // console.log('[WEBSOCKET] onmessage', event);
          onmessage(event);
        };

        ws.onclose = () => {
          // console.log('[WEBSOCKET] Connection closed', {
          //   code: event.code,
          //   reason: event.reason,
          //   wasClean: event.wasClean
          // });
          onclose();
        };

        ws.onerror = (event) => {
          // console.log('[WEBSOCKET] onerror', event);
          // Reject the promise if there's an error during connection
          reject(event);
          onerror?.(new Error('WebSocket error'));
        };
      });
    },
    getAgent: async (aid) => {
      return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}', {
        params: { path: { aid } },
        errorMsg: 'Agent Not Found',
      })) as Agent; // TODO: Remove type casting once ASI is fixed
    },
    getChatFiles: async (tid) => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}/files', {
        params: { path: { tid } },
        errorMsg: 'Failed to fetch thread files',
        silent: true,
      });
    },
    getAgentFiles: async (aid) => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}/files', {
        params: { path: { aid } },
        errorMsg: 'Failed to fetch agent files',
        silent: true,
      });
    },
    uploadFiles: async (files: File[], config: { configurable: { thread_id: string } | { assistant_id: string } }) => {
      if ('assistant_id' in config.configurable) {
        errorToast('Not implemented');
        return [];
      }

      const tid = config.configurable.thread_id;

      return agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/threads/{tid}/files', {
        body: { files: files as unknown as string[] },
        params: { path: { tid } },
        bodySerializer(body) {
          return body.files.reduce((formData, file) => {
            formData.append('files', file);
            return formData;
          }, new FormData());
        },
        errorMsg: 'Failed to upload files',
      });
    },
    downloadFile: async (tid: string, file_ref: string) => {
      // TODO: remove this manual arg types once agent-components is updated
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}/files/download/', {
        params: { path: { tid }, query: { file_ref } },
        parseAs: 'stream',
      });

      const reader = response?.getReader();
      if (!reader) return;

      const chunks: Uint8Array[] = [];
      let done = false;

      while (!done) {
        const { value, done: streamDone } = await reader.read();
        if (value) chunks.push(value);
        done = streamDone;
      }

      const blob = new Blob(chunks);

      const downloadFileAndCleanUp = () => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');

        a.href = url;
        a.download = file_ref;

        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
      };

      downloadFileAndCleanUp();
    },
    getActions: async () => {
      // TODO
      return [];
    },
    getTenant: async () => {
      return agentAPIClient.getTenant(tenantId);
    },
    getWorkItemList: async (queryOptions) => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/', {
        params: {
          query: queryOptions,
        },
      });
    },
    createWorkItem: async (payload) => {
      console.log('createWorkItem', payload);
      return agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/work-items/', {
        body: payload,
      });
    },
    getWorkItemDetails: async (workItemId) => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/{work_item_id}', {
        params: { path: { work_item_id: workItemId } },
      });
    },
    uploadWorkItemFile: async (file, workItemId) => {
      // Direct file upload - let the backend handle everything
      return await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/work-items/upload-file', {
        params: { query: workItemId ? { work_item_id: workItemId } : {} },
        body: { file: file as unknown as string },
        bodySerializer(body) {
          const formData = new FormData();
          formData.append('file', body.file);
          return formData;
        },
      });
    },
    onSuccess: (message: string) => successToast(message),
    onError: (message: string) => errorToast(message),
    onWarning: (message) => warnToast(message),
    submitFeedback: options?.isFeedbackEnabled
      ? async (
          agent_id: string,
          thread_id: string,
          // TODO: Messasge ID is not passed to ACE yet
          _message_id: string,
          feedback: { details: string; comment: string },
        ) => {
          await agentAPIClient.sendFeedback(tenantId, {
            agentId: agent_id,
            threadId: thread_id,
            feedback: feedback.details,
            comment: feedback.comment,
          });
        }
      : undefined,
  };

  // Conditionally adding showFullActionLogs callback
  if (options?.isDeveloperModeEnabled) {
    apiClient.showFullActionLogs = async (agentId, threadId, toolCallId) => {
      const htmlContent = await agentAPIClient.getActionLogHtml(tenantId, agentId, threadId, toolCallId);

      const actionLogsWindow = window.open();

      if (!actionLogsWindow) {
        errorToast('Unable to open new window for Action Logs');
        return;
      }
      actionLogsWindow.document.write(htmlContent);
      actionLogsWindow.document.close();
    };
  }

  // Conditionally adding getAgentDetails callback
  if (options?.isAgentDetailsEnabled) {
    apiClient.getAgentDetails = async (agentId) => {
      return agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}/agent-details', {
        params: { path: { aid: agentId } },
      });
    };
  }

  return apiClient;
};

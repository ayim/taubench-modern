import { Progress } from '@sema4ai/components';
import { NEW_CHAT_STARTING_MSG, streamManager } from '@sema4ai/spar-ui';
import { createFileRoute, redirect } from '@tanstack/react-router';

import { AgentNotFound } from '~/components/AgentNotFound';
import { getPreferenceKey, getUserPreferenceId, isWorkerAgent, removeUserPreferenceId } from '~/utils';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { agentId, tenantId }, location }) => {
    const agentResult = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}', {
      params: { path: { aid: agentId } },
    });

    if (!agentResult.success) {
      throw redirect({
        to: '/tenants/$tenantId/home',
        params: { tenantId },
      });
    }

    const agent = agentResult.data;

    if (isWorkerAgent(agent)) {
      throw redirect({
        to: '/tenants/$tenantId/worker/$agentId',
        params: { tenantId, agentId },
      });
    }

    const threadsResult = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/', {
      params: { query: { aid: agentId, limit: 1 } },
    });

    if (!threadsResult.success) {
      throw redirect({
        to: '/tenants/$tenantId/conversational/$agentId',
        params: { tenantId, agentId },
      });
    }

    const threads = threadsResult.data;

    /**
     * 1. If initial thread message is provided, redirect to a new thread with the message
     */
    const searchParams = new URLSearchParams(location.search);
    const initialThreadMessage = searchParams.get('initial_thread_message')?.trim();
    const startWebsocketStream = async (agentId: string) => {
      const { url, token, withBearerTokenAuth } = await agentAPIClient.getWsStreamUrl({ agentId, tenantId });
      return withBearerTokenAuth ? new WebSocket(url, ['Bearer', token]) : new WebSocket(url);
    };

    const oAuthState = await agentAPIClient.getAgentPermissions({ agentId, tenantId });
    const hasUnauthorizedProviders = oAuthState.some((provider) => !provider.isAuthorized);

    if (initialThreadMessage) {
      const newThread = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/threads/', {
        body: {
          name: 'New Chat',
          agent_id: agentId,
        },
        errorMsg: 'Failed to create thread',
      });

      if (!newThread.success || !newThread.data.thread_id) {
        throw redirect({
          to: '/tenants/$tenantId/conversational/$agentId',
          params: { tenantId, agentId },
        });
      }

      // Starting message stream
      streamManager.initiateStream({
        content: [{ kind: 'text', text: initialThreadMessage, complete: true }],
        agentId,
        queryClient,
        threadId: newThread.data.thread_id,
        startWebsocketStream,
      });

      throw redirect({
        to: '/tenants/$tenantId/conversational/$agentId/$threadId',
        params: {
          tenantId,
          agentId,
          threadId: newThread.data.thread_id,
        },
      });
    }

    /*
     * 2. Redirect to user preferred thread, if it exists
     */
    const preferedThreadId = getUserPreferenceId(getPreferenceKey({ agentId }));

    if (preferedThreadId) {
      const thread = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}', {
        params: { path: { tid: preferedThreadId } },
      });

      if (thread.success) {
        throw redirect({
          to: '/tenants/$tenantId/conversational/$agentId/$threadId',
          params: {
            tenantId,
            agentId,
            threadId: preferedThreadId,
          },
        });
      } else {
        removeUserPreferenceId(getPreferenceKey({ agentId }));
      }
    }

    /**
     * 3. If no prefered thread set, redirect to the first thread in list
     */
    if (threads?.length) {
      throw redirect({
        to: '/tenants/$tenantId/conversational/$agentId/$threadId',
        params: { tenantId, agentId, threadId: threads[0].thread_id ?? '' }, // TODO-V2: integration, remove this nullish coalescing
      });
    }

    /**
     * 4. If no threads exist, create a new one
     */

    // Only send a user message if agent has conversation starter AND OAuth permissions are authorized
    const shouldSendUserMessage = !!agent?.extra?.conversation_starter && !hasUnauthorizedProviders;
    const role = shouldSendUserMessage ? 'user' : 'agent';
    const text = shouldSendUserMessage ? (agent?.extra?.conversation_starter as string) : NEW_CHAT_STARTING_MSG;

    const newThread = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/threads/', {
      body: {
        name: 'Chat 1',
        agent_id: agentId,
        messages: [
          {
            role,
            content: [{ kind: 'text', text, complete: true }],
            complete: true,
            commited: false,
          },
        ],
      },
      errorMsg: 'Failed to create thread',
    });

    if (!newThread.success) {
      throw redirect({
        to: '/tenants/$tenantId/conversational/$agentId',
        params: { tenantId, agentId },
      });
    }

    if (shouldSendUserMessage) {
      streamManager.initiateStream({
        content: [],
        agentId,
        queryClient,
        threadId: newThread.data.thread_id ?? '',
        startWebsocketStream,
      });
    }

    throw redirect({
      to: '/tenants/$tenantId/conversational/$agentId/$threadId',
      params: {
        tenantId,
        agentId,
        threadId: newThread.data.thread_id ?? '', // TODO-V2: integration, remove this nullish coalescing
      },
    });
  },
  validateSearch: (search): { initial_thread_message?: string } => {
    return {
      initial_thread_message: search.initial_thread_message ? String(search.initial_thread_message) : undefined,
    };
  },
  pendingComponent: () => <Progress variant="page" />,
  errorComponent: AgentNotFound,
});

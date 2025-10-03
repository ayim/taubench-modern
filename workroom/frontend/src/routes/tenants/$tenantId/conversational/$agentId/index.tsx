import { Progress } from '@sema4ai/components';
import { NEW_CHAT_STARTING_MSG, streamManager } from '@sema4ai/spar-ui';
import { createFileRoute, redirect } from '@tanstack/react-router';

import { AgentNotFound } from '~/components/AgentNotFound';
import { router } from '~/components/providers/Router';
import { createSparAPIClient } from '~/lib/SparAPIClient';
import { TenantMeta } from '~/lib/tenantContext';
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
    const conversationStarter = agent.extra?.conversation_starter as string | undefined;

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
        sparAPIClient: createSparAPIClient(tenantId, undefined as unknown as TenantMeta, agentAPIClient, router),
      });

      throw redirect({
        to: '/tenants/$tenantId/conversational/$agentId/$threadId',
        params: {
          tenantId,
          agentId,
          threadId: newThread.data.thread_id,
        },
        search: {
          initial_thread_message: initialThreadMessage,
        },
      });
    }

    /*
     * 2. Redirect to user preferred thread, if it exists
     */
    const preferedThreadId = getUserPreferenceId(getPreferenceKey({ agentId }));

    if (preferedThreadId) {
      let threadExists = false;

      try {
        const thread = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}', {
          params: { path: { tid: preferedThreadId } },
          silent: true,
        });

        threadExists = !!thread;
      } catch (e) {
        console.error('Failed redirecting to preferred thread', e);
        removeUserPreferenceId(getPreferenceKey({ agentId }));
      }

      if (threadExists) {
        throw redirect({
          to: '/tenants/$tenantId/conversational/$agentId/$threadId',
          params: {
            tenantId,
            agentId,
            threadId: preferedThreadId,
          },
        });
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
    const newThread = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/threads/', {
      body: {
        name: 'Chat 1',
        agent_id: agentId,
        messages: [
          {
            role: 'agent',
            content: [{ kind: 'text', text: conversationStarter ?? NEW_CHAT_STARTING_MSG, complete: true }],
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

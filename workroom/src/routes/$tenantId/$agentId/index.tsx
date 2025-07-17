import { createFileRoute, redirect } from '@tanstack/react-router';
import { isWorkerAgent, NEW_CHAT_STARTING_MSG } from '@sema4ai/agent-components';

import { AgentNotFound } from '~/components/AgentNotFound';
import { TransitionLoader } from '~/components/Loaders';
import { getGetAgentQueryOptions } from '~/queries/agents';
import { getPreferenceKey, getUserPreferenceId, removeUserPreferenceId } from '~/utils';
import { getChatAPIClient } from '~/lib/chatAPIclient';

export const Route = createFileRoute('/$tenantId/$agentId/')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { agentId, tenantId }, location }) => {
    const agent = await queryClient.ensureQueryData(
      getGetAgentQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    const threadsResult = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/', {
      params: { query: { aid: agentId, limit: 1 } },
    });

    // Backwards compatibillity for Agent Backend < 1.2.1
    const threads = threadsResult.filter((thread) => thread.agent_id === agentId);

    const chatApiClient = getChatAPIClient(tenantId, agentAPIClient);

    /**
     * 1. Conversational agents: If initial thread message is provided, redirect to a new thread with the message
     */
    const searchParams = new URLSearchParams(location.search);
    const initialThreadMessage = searchParams.get('initial_thread_message')?.trim();

    if (!isWorkerAgent(agent) && initialThreadMessage) {
      const newThread = await chatApiClient.createChat(
        agentId,
        'New Chat',
        // TODO: v2 integration, ask to add welcome_message in types
        (agent.metadata?.welcome_message as string) ?? NEW_CHAT_STARTING_MSG,
      );

      throw redirect({
        to: '/$tenantId/$agentId/$threadId',
        params: {
          tenantId,
          agentId,
          threadId: newThread.thread_id ?? '', // TODO: v2 integration, remove this nullish coalescing
        },
        search: {
          initial_thread_message: initialThreadMessage,
        },
      });
    }

    /*
     * 2. Conversational and Worker Agents: Redirect to user preferred thread, if it exists
     */
    const preferedThreadId = getUserPreferenceId(getPreferenceKey(agent));

    if (preferedThreadId) {
      let threadExists = false;

      try {
        let threadId = preferedThreadId;

        if (isWorkerAgent(agent)) {
          const parts = preferedThreadId.split('_');
          if (parts.length === 2) {
            [, threadId] = parts;
          } else {
            throw new Error('Invalid prefered thread id for Worker Agent');
          }
        }

        const thread = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}', {
          params: { path: { tid: threadId } },
          silent: true,
        });

        threadExists = !!thread;
      } catch (e) {
        removeUserPreferenceId(getPreferenceKey(agent));
      }

      if (threadExists) {
        throw redirect({
          to: '/$tenantId/$agentId/$threadId',
          params: {
            tenantId,
            agentId,
            threadId: preferedThreadId,
          },
        });
      }
    }

    /**
     * 3. Worker Agents: If no prefered thread set, redirect to dashboard view
     */

    if (isWorkerAgent(agent)) {
      throw redirect({
        to: '/$tenantId/$agentId/$threadId',
        params: {
          tenantId,
          agentId,
          threadId: 'dashboard',
        },
      });
    }

    /**
     * 4. Conversational Agents: If no prefered thread set, redirect to the first thread in list
     */
    if (threads?.length) {
      throw redirect({
        to: '/$tenantId/$agentId/$threadId',
        params: { tenantId, agentId, threadId: threads[0].thread_id ?? '' }, // TODO: v2 integration, remove this nullish coalescing
      });
    }

    /**
     * 5. Conversational Agents: If no threads exist, create a new one
     */
    const newThread = await chatApiClient.createChat(
      agentId,
      'Chat 1',
      // TODO: v2 integration, ask to add welcome_message in types
      (agent.metadata?.welcome_message as string) ?? NEW_CHAT_STARTING_MSG,
    );

    throw redirect({
      to: '/$tenantId/$agentId/$threadId',
      params: {
        tenantId,
        agentId,
        threadId: newThread.thread_id ?? '', // TODO: v2 integration, remove this nullish coalescing
      },
    });
  },
  validateSearch: (search): { initial_thread_message?: string } => {
    return {
      initial_thread_message: search.initial_thread_message ? String(search.initial_thread_message) : undefined,
    };
  },
  pendingComponent: TransitionLoader,
  errorComponent: AgentNotFound,
});

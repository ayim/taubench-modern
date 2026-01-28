import { Progress } from '@sema4ai/components';
import { NEW_CHAT_STARTING_MSG } from '~/lib/constants';
import { streamManager } from '~/hooks/useMessageStream';
import { createFileRoute, redirect } from '@tanstack/react-router';

import { AgentNotFound } from '~/components/AgentNotFound';
import { isValidRoute } from '~/lib/utils';
import { agentQueryOptions } from '~/queries/agents';
import { getThreadQueryOptions, listThreadsQueryOptions } from '~/queries/thread';
import { getPreferenceKey, getUserPreferenceId, isWorkerAgent, removeUserPreferenceId } from '~/utils';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { agentId, tenantId }, location }) => {
    const agent = await queryClient.fetchQuery(agentQueryOptions({ agentAPIClient, agentId }));

    if (!agent) {
      throw redirect({
        to: '/tenants/$tenantId/home',
        params: { tenantId },
      });
    }

    if (isWorkerAgent(agent)) {
      throw redirect({
        to: '/tenants/$tenantId/worker/$agentId',
        params: { tenantId, agentId },
      });
    }

    const threadsResult = await queryClient.fetchQuery(
      listThreadsQueryOptions({ agentId, params: { limit: 100 }, agentAPIClient }),
    );
    if (!threadsResult.success) {
      throw redirect({
        to: '/tenants/$tenantId/conversational/$agentId',
        params: { tenantId, agentId },
      });
    }

    const threads = threadsResult.data;

    // Filter out evaluation threads (threads with scenario_id in metadata)
    // Note: We check the first 100 threads for user-initiated threads.
    // If none are found, we'll create a new thread below.
    const userInitiatedThreads = threads?.filter((thread) => !thread.metadata?.scenario_id);

    /**
     * 1. If initial thread message is provided, redirect to a new thread with the message
     */
    const searchParams = new URLSearchParams(location.search);
    const initialThreadMessage = searchParams.get('initial_thread_message')?.trim();

    const targetRoute = `/tenants/$tenantId/conversational/$agentId/$threadId/${searchParams.get('threadView')?.trim() || ''}`;
    const threadRoute = isValidRoute(targetRoute)
      ? targetRoute
      : '/tenants/$tenantId/conversational/$agentId/$threadId';

    const startWebsocketStream = async (aId: string) => {
      const { url, token, withBearerTokenAuth } = await agentAPIClient.getWsStreamUrl({ agentId: aId });
      return withBearerTokenAuth ? new WebSocket(url, ['Bearer', token]) : new WebSocket(url);
    };

    const oAuthState = await agentAPIClient.getAgentPermissions({ agentId });
    const hasUnauthorizedProviders = oAuthState.some((provider) => !provider.isAuthorized);

    if (initialThreadMessage) {
      const newThread = await agentAPIClient.agentFetch('post', '/api/v2/threads/', {
        body: {
          name: 'New Conversation',
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
        to: threadRoute,
        params: {
          tenantId,
          agentId,
          threadId: newThread.data.thread_id,
        },
      });
    }

    /*
     * 2. Redirect to user preferred thread, if it exists and is not an evaluation thread
     */
    const preferedThreadId = getUserPreferenceId(getPreferenceKey({ agentId }));

    if (preferedThreadId) {
      const thread = await queryClient.fetchQuery(
        getThreadQueryOptions({ threadId: preferedThreadId, agentAPIClient }),
      );

      if (thread.success) {
        // Check if this is an evaluation thread (has scenario_id in metadata)
        const isEvaluationThread = Boolean(thread.data.metadata?.scenario_id);

        if (isEvaluationThread) {
          // Evaluation threads should not be used as preferred threads
          // Remove the preference and continue to next step (first user thread)
          removeUserPreferenceId(getPreferenceKey({ agentId }));
        } else {
          throw redirect({
            to: threadRoute,
            params: {
              tenantId,
              agentId,
              threadId: preferedThreadId,
            },
          });
        }
      } else {
        removeUserPreferenceId(getPreferenceKey({ agentId }));
      }
    }

    /**
     * 3. If no prefered thread set, redirect to the first user-initiated thread in list
     */
    if (userInitiatedThreads?.length) {
      throw redirect({
        to: threadRoute,
        params: { tenantId, agentId, threadId: userInitiatedThreads[0].thread_id ?? '' }, // TODO-V2: integration, remove this nullish coalescing
      });
    }

    /**
     * 4. If no threads exist, create a new one
     */

    // Only send a user message if agent has conversation starter AND OAuth permissions are authorized
    const shouldSendUserMessage = !!agent?.extra?.conversation_starter && !hasUnauthorizedProviders;
    const role = shouldSendUserMessage ? 'user' : 'agent';
    const text = shouldSendUserMessage ? (agent?.extra?.conversation_starter as string) : NEW_CHAT_STARTING_MSG;

    const newThread = await agentAPIClient.agentFetch('post', '/api/v2/threads/', {
      body: {
        name: 'Conversation 1',
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
      to: threadRoute,
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

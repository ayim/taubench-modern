import { Box, Button, EmptyState } from '@sema4ai/components';
import { useQuery } from '@tanstack/react-query';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import errorIllustration from '~/assets/error.svg';
import { TransitionLoader } from '~/components/Loaders';
import { getAgentMetaQueryOptions, getGetAgentQueryOptions } from '~/queries/agents';
import { getListAgentPermissionsQueryOptions } from '~/queries/permissions';
import { getPreferenceKey, isWorkerAgent, removeUserPreferenceId, setUserPreferenceId } from '~/utils';
import { ChatPage } from './components/ChatPage';
import { useEffect, useState } from 'react';

// pathParam /:threadId will have value of workitem_id for the worker agent
export const Route = createFileRoute('/tenants/$tenantId/$agentId/$threadId')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { agentId, tenantId, threadId } }) => {
    const permissions = await queryClient.ensureQueryData(
      getListAgentPermissionsQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    const agent = await queryClient.ensureQueryData(
      getGetAgentQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    const agentMeta = await queryClient.ensureQueryData(
      getAgentMetaQueryOptions({
        agentId,
        tenantId,
        agentAPIClient,
      }),
    );

    let effectiveThreadId: string | undefined = undefined;
    let effectiveWorkItemId: string | undefined = undefined;

    if (isWorkerAgent(agent) && threadId !== 'dashboard') {
      // threadId will be : workitemId_threadId
      const parts = threadId.split('_');
      if (parts.length === 2) {
        [effectiveWorkItemId, effectiveThreadId] = parts;
      } else {
        // parts.length = 1: handling scenario where
        // agent was already opened before this update
        removeUserPreferenceId(getPreferenceKey(agent));
      }
    } else {
      effectiveThreadId = threadId;
    }

    setUserPreferenceId(getPreferenceKey(agent), threadId);

    return { agentMeta, permissions, effectiveThreadId, effectiveWorkItemId };
  },
  validateSearch: (search): { initial_thread_message?: string } => {
    return {
      initial_thread_message: search.initial_thread_message ? String(search.initial_thread_message) : undefined,
    };
  },
  component: View,
  pendingComponent: TransitionLoader,
});

function View() {
  const navigate = useNavigate({ from: Route.fullPath });
  const { agentId, tenantId, threadId } = Route.useParams();
  const { initial_thread_message } = Route.useSearch();
  const {
    agentMeta: initialAgentMeta,
    effectiveThreadId,
    permissions: initialPermissions,
    effectiveWorkItemId,
  } = Route.useLoaderData();
  const { agentAPIClient } = Route.useRouteContext();
  const [initialThreadMessage, setInitialThreadMessage] = useState(initial_thread_message);

  const { data: permissions } = useQuery(
    getListAgentPermissionsQueryOptions({
      agentId,
      tenantId,
      agentAPIClient,
      initialData: initialPermissions,
    }),
  );

  const { data: agentMeta, isLoading: isAgentMetaLoading } = useQuery(
    getAgentMetaQueryOptions({
      agentId,
      tenantId,
      agentAPIClient,
      initialData: initialAgentMeta,
    }),
  );

  useEffect(() => {
    setInitialThreadMessage(undefined);
  }, [threadId]);

  useEffect(() => {
    if (initial_thread_message) {
      setInitialThreadMessage(initial_thread_message);
      navigate({
        search: {},
      });
    }
  }, [initial_thread_message, navigate]);

  if (isAgentMetaLoading) {
    return <TransitionLoader />;
  }

  if (agentMeta?.workroomUi && !agentMeta.workroomUi.conversations.enabled) {
    return (
      <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="calc(100% - 72px)">
        <EmptyState
          illustration={<img src={errorIllustration} loading="lazy" alt="" />}
          title="Conversations are not enabled"
          description={agentMeta.workroomUi.conversations.message}
          action={
            <Link to="/tenants/$tenantId/home" params={{ tenantId }}>
              <Button forwardedAs="span" round>
                Go to Home
              </Button>
            </Link>
          }
        />
      </Box>
    );
  }

  return (
    <ChatPage
      {...{
        tenantId,
        threadId: effectiveThreadId,
        workItemId: effectiveWorkItemId,
        agentId,
        agentMeta,
        agentAPIClient,
        permissions,
        initialThreadMessage,
      }}
    />
  );
}

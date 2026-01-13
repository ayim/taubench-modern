import { AgentOAuthProviderState, SparAPIClient, SparUIFeatureFlag, SparUIRoutes } from '@sema4ai/spar-ui';
import { useParams, useRouter, useSearch } from '@tanstack/react-router';

import { FileRouteTypes } from '~/routeTree.gen';
import { router } from '~/components/providers/Router';
import { AgentAPIClient } from './AgentAPIClient';
import { TenantMeta } from './tenantContext';
import { useAgentMetaContext } from './agentMetaContext';
const routesMapping = {
  '/thread/$agentId/$threadId': '/tenants/$tenantId/conversational/$agentId/$threadId',
  '/thread/$agentId/$threadId/data-frames': '/tenants/$tenantId/conversational/$agentId/$threadId/data-frames',
  '/thread/$agentId/$threadId/evaluations': '/tenants/$tenantId/conversational/$agentId/$threadId/evaluations',
  '/thread/$agentId/$threadId/chat-details': '/tenants/$tenantId/conversational/$agentId/$threadId/chat-details',
  '/thread/$agentId/$threadId/files': '/tenants/$tenantId/conversational/$agentId/$threadId/files',
  '/thread/$agentId': '/tenants/$tenantId/conversational/$agentId',
  '/workItem/$agentId': '/tenants/$tenantId/worker/$agentId',
  '/workItem/$agentId/create': '/tenants/$tenantId/worker/$agentId/create',
  '/workItem/$agentId/$workItemId/$threadId': '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId',
  '/workItem/$agentId/$workItemId/$threadId/chat-details':
    '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/chat-details',
  '/workItem/$agentId/$workItemId/$threadId/files': '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/files',
  '/workItem/$agentId/$workItemId/$threadId/workitem-details':
    '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/workitem-details',
  '/workItem/$agentId/$workItemId/$threadId/data-frames':
    '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/data-frames',
  '/workItem/$agentId/$workItemId': '/tenants/$tenantId/worker/$agentId/$workItemId',
  '/workItems/list': '/tenants/$tenantId/workItems/list',
  '/data-connections': '/tenants/$tenantId/data-access/data-connections',
  '/data-connections/create': '/tenants/$tenantId/data-access/data-connections/create',
  '/data-connections/$dataConnectionId': '/tenants/$tenantId/data-access/data-connections/$dataConnectionId',
  '/home': '/tenants/$tenantId/home',
} satisfies Record<keyof SparUIRoutes, FileRouteTypes['to']>;

export const createSparAPIClient = (
  tenantId: string,
  tenantMeta: TenantMeta,
  agentAPIClient: AgentAPIClient,
  routerInstance: typeof router,
): SparAPIClient => ({
  useFeatureFlag: (feature: SparUIFeatureFlag) => {
    const agentMeta = useAgentMetaContext();
    const featureFlagFallback = { enabled: false };

    switch (feature) {
      case SparUIFeatureFlag.showActionLogs:
        return { enabled: tenantMeta.features.developerMode.enabled };
      case SparUIFeatureFlag.deploymentWizard:
        return { enabled: tenantMeta.features.deploymentWizard.enabled };
      case SparUIFeatureFlag.canCreateAgents:
        return { enabled: tenantMeta.features.agentAuthoring.enabled };
      case SparUIFeatureFlag.canConfigureAgents:
        return { enabled: tenantMeta.features.agentConfiguration.enabled };
      case SparUIFeatureFlag.agentDetails:
        return { enabled: tenantMeta.features.agentDetails.enabled };
      case SparUIFeatureFlag.documentIntelligence:
        return { enabled: tenantMeta.features.documentIntelligence.enabled };
      case SparUIFeatureFlag.semanticDataModels:
        return { enabled: tenantMeta.features.semanticDataModels.enabled };
      case SparUIFeatureFlag.agentFeedback:
        return agentMeta?.workroomUi?.feedback ?? featureFlagFallback;
      case SparUIFeatureFlag.agentChatInput:
        return agentMeta?.workroomUi?.chatInput ?? featureFlagFallback;
      case SparUIFeatureFlag.violetAgentChat:
        // Keep behind developer mode for now; adjust when a dedicated flag exists in tenant meta
        return { enabled: tenantMeta.features.developerMode.enabled };
      default:
        feature satisfies never;
        return featureFlagFallback;
    }
  },

  queryAgentServer: (method, path, params) => {
    // TODO-V2: Getting "Expression produces a union type that is too complex to represent" error since @sema4ai/agent-server-interface version 2.0.37
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    return agentAPIClient.agentFetch(tenantId, method, path, params);
  },

  startWebsocketStream: async (agentId: string) => {
    const { url, token, withBearerTokenAuth } = await agentAPIClient.getWsStreamUrl({ agentId, tenantId });

    return withBearerTokenAuth ? new WebSocket(url, ['Bearer', token]) : new WebSocket(url);
  },

  navigate: ({ to, params, search }) => {
    const route = routesMapping[to];

    routerInstance.navigate({
      to: route,
      params: { ...params, tenantId },
      ...(search && { search }),
    });
  },

  openActionLogs: async (params) => {
    const response = await agentAPIClient.getActionLogHtml({ tenantId, ...params });

    if (!response.success) {
      return response;
    }

    const actionLogsWindow = window.open();

    if (!actionLogsWindow) {
      return {
        success: false,
        error: {
          message: 'Unable to open the action logs',
        },
      };
    }

    actionLogsWindow.document.write(response.data.html);
    actionLogsWindow.document.close();

    return { success: true };
  },

  getAgentOAuthState: async ({ agentId }) => {
    // TODO-V2: Resolve type casting, Workroom interface should rely on @sema4ai/oauth-client for OAuth provider type (single source of truth)
    return agentAPIClient.getAgentPermissions({ agentId, tenantId }) as Promise<AgentOAuthProviderState[]>;
  },

  authorizeAgentOAuth: async ({ uri }) => {
    window.location.href = uri;
  },

  deleteAgentOAuth: async ({ agentId, connectionId }) => {
    await agentAPIClient.deleteOAuthConnection({ agentId, tenantId, connectionId });
  },

  useParamsFn: <T extends keyof SparUIRoutes>() => {
    const params = useParams({ strict: false });
    return params as SparUIRoutes[T];
  },

  useRouteFn: (to, params) => {
    const route = routesMapping[to];
    const router = useRouter();

    const { href } = router.buildLocation({ to: route, params: { tenantId, ...params } as never });
    const current = router.state.matches.some((match) => match.pathname === href);

    return {
      href,
      current,
    };
  },

  useSearchParamsFn: () => {
    return useSearch({ strict: false });
  },

  usePathnameFn: () => {
    const router = useRouter();
    return router.state.location.pathname;
  },

  getWorkItemAPIURL: async () => {
    return {
      success: false,
      error: {
        message: 'Work Item API URL not available',
      },
    };
  },

  sendFeedback: async (props) => {
    return agentAPIClient.sendFeedback(tenantId, props);
  },
});

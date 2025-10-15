import { AgentOAuthProviderState, SparAPIClient, SparUIFeatureFlag, SparUIRoutes } from '@sema4ai/spar-ui';
import { useParams, useRouter } from '@tanstack/react-router';

import { FileRouteTypes } from '~/routeTree.gen';
import { router } from '~/components/providers/Router';
import { AgentAPIClient } from './AgentAPIClient';
import { TenantMeta } from './tenantContext';
import { useAgentMetaContext } from './agentMetaContext';
const routesMapping = {
  '/thread/$agentId/$threadId': '/tenants/$tenantId/conversational/$agentId/$threadId',
  '/thread/$agentId/$threadId/data-frames': '/tenants/$tenantId/conversational/$agentId/$threadId/data-frames',
  '/thread/$agentId': '/tenants/$tenantId/conversational/$agentId',
  '/workItem/$agentId': '/tenants/$tenantId/worker/$agentId',
  '/workItem/$agentId/create': '/tenants/$tenantId/worker/$agentId/create',
  '/workItem/$agentId/$workItemId/$threadId': '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId',
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
  getFeatureFlag: (feature: SparUIFeatureFlag) => {
    const agentMeta = useAgentMetaContext();

    switch (feature) {
      case SparUIFeatureFlag.showActionLogs:
        return tenantMeta.features.developerMode.enabled;
      case SparUIFeatureFlag.deploymentWizard:
        return tenantMeta.features.deploymentWizard.enabled;
      case SparUIFeatureFlag.showFeedback:
        if (!agentMeta) {
          return false;
        }
        return agentMeta.workroomUi?.feedback?.enabled ?? false;
      case SparUIFeatureFlag.canEditAgent:
        return tenantMeta.features.agentAuthoring.enabled;
      case SparUIFeatureFlag.agentDetails:
        return tenantMeta.features.agentDetails.enabled;
      default:
        return false;
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

  navigate: ({ to, params }) => {
    const route = routesMapping[to];

    routerInstance.navigate({
      to: route,
      params: { ...params, tenantId },
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

  downloadFile: async ({ threadId, name, type }) => {
    const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/threads/{tid}/files/download/', {
      params: { path: { tid: threadId }, query: { file_ref: name } },
      parseAs: 'stream',
    });

    if (!response.success) {
      throw new Error('Failed to download file');
    }

    const reader = (response.data as ReadableStream)?.getReader();
    if (!reader) return;

    const chunks: BlobPart[] = [];
    let done = false;

    while (!done) {
      const { value, done: streamDone } = await reader.read();
      if (value) chunks.push(value);
      done = streamDone;
    }

    const blob = new Blob(chunks);

    if (type === 'inline') {
      const file = new File([blob], name);
      return { file };
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

    return;
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

import { AgentOAuthProviderState, SparAPIClient, SparUIFeatureFlag, SparUIRoutes } from '@sema4ai/spar-ui';
import { useParams, useRouter } from '@tanstack/react-router';

import { FileRouteTypes } from '~/routeTree.gen';
import { router } from '~/components/providers/Router';
import { AgentAPIClient } from './AgentAPIClient';
import { TenantMeta } from './tenantContext';

const routesMapping = {
  '/thread/$agentId/$threadId': '/tenants/$tenantId/conversational/$agentId/$threadId',
  '/thread/$agentId': '/tenants/$tenantId/conversational/$agentId',
} satisfies Record<keyof SparUIRoutes, FileRouteTypes['id']>;

export const createSparAPIClient = (
  tenantId: string,
  tenantMeta: TenantMeta,
  agentAPIClient: AgentAPIClient,
  routerInstance: typeof router,
): SparAPIClient => ({
  getFeatureFlag: (feature: SparUIFeatureFlag) => {
    switch (feature) {
      case SparUIFeatureFlag.showActionLogs:
        return tenantMeta.features.developerMode.enabled;
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
    const html = await agentAPIClient.getActionLogHtml({ tenantId, ...params });

    const actionLogsWindow = window.open();

    if (!actionLogsWindow) {
      return false;
    }

    actionLogsWindow.document.write(html);
    actionLogsWindow.document.close();

    return true;
  },

  downloadFile: async ({ threadId, name }) => {
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
  },

  getAgentOAuthState: async ({ agentId }) => {
    // TODO-V2: Resolve type casting, Workroom interface should rely on @sema4ai/oauth-client for OAuth provider type (single source of truth)
    return agentAPIClient.getAgentPermissions({ agentId, tenantId }) as Promise<AgentOAuthProviderState[]>;
  },

  authorizeAgentOAuth: async ({ uri }) => {
    window.location.href = uri;
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
});

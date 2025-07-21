import { createWorkroomClient, AgentOAuthPermission, operations } from '@sema4ai/workroom-interface';
import { DocumentIntelligenceSchema } from '@sema4ai/document-intelligence-interface';
import { WorkItemsSchema } from '@sema4ai/work-items-interface';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { paths as agentServerPaths } from '@sema4ai/agent-server-interface';
import createFetchClient, { ClientMethod, FetchResponse, MaybeOptionalInit } from 'openapi-fetch';
import { HttpMethod, MediaType, PathsWithMethod, RequiredKeysOf } from 'openapi-typescript-helpers';
import { UserTenant } from '~/queries/tenants';
import { errorToast } from '~/utils/toasts';
import { RequestError } from './Error';

// Reference:
// https://github.com/openapi-ts/openapi-typescript/blob/fdc6d229e995b6009619835530ac74487fda48ef/packages/openapi-fetch/src/index.d.ts#L165
type InitParam<Init> =
  RequiredKeysOf<Init> extends never ? [(Init & { [key: string]: unknown })?] : [Init & { [key: string]: unknown }];

export type Meta =
  | {
      deploymentType: undefined;
      realm: string;
      clientId: string;
      enableRefreshTokens: boolean;
      oidcServerDiscoveryURI: string;
      instanceId: string;
      workroomTokenExchangeUrl: string;
      workroomTenantListUrl: string;
      branding?: {
        logoUrl: string;
        agentAvatarUrl: string;
      };
    }
  | {
      deploymentType: 'spcs' | 'spar';
      workroomTenantListUrl: string;
      branding?: {
        logoUrl: string;
        agentAvatarUrl: string;
      };
    };

type WorkroomToken = {
  token: string;
  expiresAt: string;
};

// eslint-disable-next-line @typescript-eslint/ban-types
type EmptyObjectType = {};

export class AgentAPIClient {
  private getUserToken: () => Promise<string | undefined>;
  private workroomToken: WorkroomToken | undefined;
  private meta: Meta | null = null;
  private tenants: UserTenant[] = [];

  constructor(getUserToken: () => Promise<string | undefined>) {
    this.getUserToken = getUserToken;
  }

  public async getMeta(): Promise<Meta> {
    if (this.meta) {
      return this.meta;
    }

    if (import.meta.env.MODE === 'development') {
      console.warn('This should not be invoked in prod!', { deploymentType: import.meta.env.VITE_DEPLOYMENT_TYPE });
      return {
        deploymentType: import.meta.env.VITE_DEPLOYMENT_TYPE,
        realm: import.meta.env.VITE_DEV_OIDC_REALM,
        clientId: import.meta.env.VITE_DEV_OIDC_CLIENT_ID,
        enableRefreshTokens: import.meta.env.VITE_DEV_OIDC_ALLOW_REFRESH_TOKENS_WITH_ROTATION,
        oidcServerDiscoveryURI: import.meta.env.VITE_DEV_OIDC_DISCOVERY_URI,
        instanceId: import.meta.env.VITE_INSTANCE_ID,
        workroomTokenExchangeUrl: import.meta.env.VITE_DEV_WORKROOM_TOKEN_EXCHANGE_URL,
        workroomTenantListUrl: import.meta.env.VITE_DEV_WORKROOM_TENANT_LIST_URL,
      };
    }

    const url = new URL('/meta', window.location.href).href;
    const response = await fetch(url, {
      method: 'GET',
    }).then(async (res) => await res.json());

    this.meta = response as Meta;

    return this.meta;
  }

  private async getWorkroomToken() {
    if (this.workroomToken) {
      const isTokenStillValid = new Date(this.workroomToken.expiresAt).valueOf() - new Date().valueOf() > 60000;
      if (isTokenStillValid) {
        return this.workroomToken.token;
      }
    }

    const metaContent = await this.getMeta();

    if (metaContent.deploymentType !== undefined) {
      metaContent.deploymentType satisfies 'spar' | 'spcs';
      return metaContent.deploymentType === 'spar' ? `TO_BE_DEFINED` : 'SPCS_AUTH_VIA_COOKIES';
    }

    const userToken = await this.getUserToken();

    if (!userToken) {
      throw new RequestError(401, 'Authorization failed');
    }

    const response: WorkroomToken = await fetch(metaContent.workroomTokenExchangeUrl, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${userToken}`,
      },
    }).then((res) => res.json());

    this.workroomToken = response;

    return response.token;
  }

  public async getTenant(tenantId: string): Promise<UserTenant | undefined> {
    const cached = this.tenants.find((curr) => curr.id === tenantId);

    if (cached) {
      return cached;
    }

    await this.getTenants();
    const tenant = this.tenants.find((curr) => curr.id === tenantId);

    return tenant;
  }

  public async getTenants(): Promise<UserTenant[]> {
    const userToken = await this.getUserToken();
    const { workroomTenantListUrl } = await this.getMeta();

    const response = await fetch(workroomTenantListUrl, {
      method: 'GET',
      headers: { authorization: `Bearer ${userToken}` },
    }).then((res) => res.json());

    this.tenants = response.data;

    return response.data;
  }

  public async getAgentMeta({
    agentId,
    tenantId,
  }: {
    tenantId: string;
    agentId: string;
  }): Promise<operations['getAgentMeta']['responses'][200]['content']['application/json']> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/agents/{agentId}/meta', {
      params: {
        path: {
          tenantId,
          agentId,
        },
      },
    });

    if (response.error) {
      throw new RequestError(response.response.status, response.error.error.message);
    }

    return response.data;
  }

  public async getAgentDetails({
    agentId,
    tenantId,
  }: {
    tenantId: string;
    agentId: string;
  }): Promise<operations['getAgentDetails']['responses'][200]['content']['application/json']> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/agents/{agentId}/details', {
      params: {
        path: {
          tenantId,
          agentId,
        },
      },
    });
    if (response.error) {
      throw new RequestError(response.response.status, response.error.error.message);
    }

    return response.data;
  }

  public async getAgentPermissions({
    agentId,
    tenantId,
  }: {
    tenantId: string;
    agentId: string;
  }): Promise<AgentOAuthPermission[]> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/agents/{agentId}/me/oauth/permissions', {
      params: {
        path: {
          tenantId,
          agentId,
        },
        query: {
          redirectUri: `${window.location.protocol}//${window.location.host}/oauth`,
        },
      },
    });

    if (response.error) {
      return [];
    }

    return response.data;
  }

  public async deleteOAuthConnection({
    tenantId,
    agentId,
    connectionId,
  }: {
    tenantId: string;
    agentId: string;
    connectionId: string;
  }): Promise<{ agentId: string; connectionId: string }> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.DELETE(
      '/tenants/{tenantId}/workroom/agents/{agentId}/me/oauth/connections/{connectionId}',
      {
        params: {
          path: {
            tenantId,
            agentId,
            connectionId,
          },
        },
      },
    );

    if (response.error) {
      throw new RequestError(response.response.status, response.error.error.message);
    }

    return response.data;
  }

  public async authorizeOAuth({
    tenantId,
  }: {
    tenantId: string;
  }): Promise<{ success: true } | { success: false; error: { code: string } }> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);
    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }
    const params = new URL(document.location.toString()).searchParams;

    // Fix the scope by replacing single slashes with double slashes after 'https:'
    // google will return scope=https:/www... for some reason
    const fixUrlEncoding = (s: string) => s.replace(/https:\/(?!\/)/g, 'https://');
    const scope = fixUrlEncoding(params.get('scope') || '');

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/oauth/authorize', {
      params: {
        path: {
          tenantId,
        },
        query: {
          code: params.get('code') as string,
          state: params.get('state') as string,
          scope: scope,
        },
      },
    });

    if (response.error) {
      return {
        success: false,
        error: {
          code: response.error.error.code,
        },
      } as const;
    }

    return {
      success: true,
    } as const;
  }

  public async sendFeedback(
    tenantId: string,
    payload: {
      agentId: string;
      threadId: string;
      feedback: string;
      comment: string;
    },
  ) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.POST('/tenants/{tenantId}/workroom/feedback', {
      params: {
        path: {
          tenantId,
        },
      },
      body: payload,
    });

    return !response.error;
  }

  public async listAuditLogs(tenantId: string) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/audit-logs', {
      params: {
        path: {
          tenantId,
        },
      },
    });

    if (response.error) {
      return [];
    }

    return response.data;
  }

  private createClient<Paths extends EmptyObjectType>(pathIdentifier: string) {
    return (function <Paths extends Record<string, Record<HttpMethod, EmptyObjectType>>>() {
      return async function <
        Method extends HttpMethod,
        Path extends PathsWithMethod<Paths, Method>,
        Init extends MaybeOptionalInit<Paths[Path], Method>,
      >(
        this: AgentAPIClient,
        tenantId: string,
        method: Method,
        path: Path,
        ...init: InitParam<Init & { errorMsg?: string; toastMessage?: string; silent?: boolean }>
      ) {
        const workroomToken = await this.getWorkroomToken();
        const tenant = await this.getTenant(tenantId);
        if (!tenant) {
          throw new RequestError(404, 'Workspace not found');
        }

        // TODO: Extract into utils: specified in two places
        // The tenants path (first parameter) needs to be joined relatively
        // to the URL provided in the tenant environment result. Resolving
        // URLs with the URL class is tricky as leading and trailing slahses
        // affect the resolution. The first path must not start with a slash
        // (relative), and the tenant URL must end with one for the resolution
        // to work correctly.
        const url = new URL(
          `tenants/${tenant.id}/${pathIdentifier}`,
          tenant.environment.url.endsWith('/') ? tenant.environment.url : `${tenant.environment.url}/`,
        ).href;

        const client = createFetchClient<Paths>({
          baseUrl: url,
          headers: {
            Authorization: `Bearer ${workroomToken}`,
          },
        });

        const apiResponse = (await (
          client[method.toUpperCase() as Uppercase<HttpMethod>] as ClientMethod<EmptyObjectType, Method, MediaType>
        )(
          path as never,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          ...(init as any),
        )) as FetchResponse<Paths[Path][Method], Init, MediaType>;

        if (apiResponse.data !== undefined) {
          return apiResponse.data;
        }

        /**
         * For reponse with 204 status code,
         * we don't receive any data, so we return null
         */
        if (!apiResponse.error && apiResponse.response.status === 204) {
          return undefined as unknown as never;
        }

        // If errorMsg is provided in init argument then show it in toast
        let errorStr = '';

        const errorDetails = init?.[0] ?? null;

        if (errorDetails) {
          errorStr = errorDetails.errorMsg ?? JSON.stringify(apiResponse.error);
          !errorDetails.silent && errorToast(errorDetails.toastMessage ?? errorStr);
        }

        const errorMessage = (() => {
          try {
            const parsed = JSON.parse(errorStr);
            return parsed.detail || parsed.message || errorStr;
          } catch {
            return errorStr;
          }
        })();

        throw new RequestError(apiResponse.response.status, errorMessage);
      };
    })<Paths>();
  }

  public get agentFetch() {
    return this.createClient<agentServerPaths>('agents');
  }

  public get docIntelliFetch() {
    return this.createClient<DocumentIntelligenceSchema.paths>('documents');
  }

  public get agentEventsFetch() {
    return this.createClient<WorkItemsSchema.paths>('events');
  }

  public async startStream({
    tenantId,
    args,
  }: {
    tenantId: string;
    args: {
      input?: string;
      thread_id: string;
      onmessage?: (event: unknown) => void;
      onopen?: (response: Response) => Promise<void>;
      onclose?: () => void;
      onerror?: (error: Error) => void;
    };
  }) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const { input, thread_id, ...rest } = args;

    // TODO: Extract into utils: specified in two places
    // The tenants path (first parameter) needs to be joined relatively
    // to the URL provided in the tenant environment result. Resolving
    // URLs with the URL class is tricky as leading and trailing slahses
    // affect the resolution. The first path must not start with a slash
    // (relative), and the tenant URL must end with one for the resolution
    // to work correctly.

    const url = new URL(
      `tenants/${tenant.id}/agents/api/v2/runs/stream`,
      tenant.environment.url.endsWith('/') ? tenant.environment.url : `${tenant.environment.url}/`,
    ).href;
    await fetchEventSource(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${workroomToken}` },
      body: JSON.stringify({ input, thread_id }),
      openWhenHidden: true,
      ...rest,
    });
  }

  private async prepareForRequest(tenantId: string) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    return { workroomToken, tenant };
  }

  public async getTenantMeta(tenantId: string) {
    const { tenant, workroomToken } = await this.prepareForRequest(tenantId);

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/meta', {
      params: {
        path: {
          tenantId,
        },
      },
    });

    if (response.error) {
      errorToast('Unable to fetch Tenant Meta');
      return;
    }

    return response.data;
  }

  public async getActionLogHtml(tenantId: string, agentId: string, threadId: string, toolCallId: string) {
    const { tenant, workroomToken } = await this.prepareForRequest(tenantId);

    const workroomClient = createWorkroomClient({
      baseUrl: tenant.environment.url,
      bearerToken: workroomToken,
    });

    const getActionLogs = await workroomClient.GET(
      '/tenants/{tenantId}/workroom/agents/{agentId}/threads/{threadId}/action-invocations/{actionInvocationId}',
      {
        params: {
          path: {
            tenantId,
            agentId,
            threadId,
            actionInvocationId: toolCallId,
          },
        },
        parseAs: 'stream',
      },
    );

    if (![200, 304].includes(getActionLogs.response.status) || !getActionLogs.data) {
      errorToast('Unable to fetch Action Log Html');
      throw new RequestError(getActionLogs.response.status, '');
    }

    const reader = getActionLogs.data.getReader();
    const decoder = new TextDecoder();
    const chunks: string[] = [];

    let done = false;

    while (!done) {
      const { value, done: streamDone } = await reader.read();
      done = streamDone;

      if (value) {
        const chunk = decoder.decode(value, { stream: true });
        chunks.push(chunk);
      }
    }

    return chunks.join('');
  }

  /**
   * This method gives URL to connect web socket to the agent server
   * another approach can be creating WebSocket object in this method and
   * return it.
   */
  public async getWsStreamUrl({ agentId, tenantId }: { agentId: string; tenantId: string }) {
    const tenant = await this.getTenant(tenantId);
    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomToken = await this.getWorkroomToken();

    const withBearerTokenAuth = (await this.getMeta()).deploymentType !== 'spar';

    const url = new URL(
      `tenants/${tenant.id}/agents/api/v2/runs/${agentId}/stream`,
      tenant.environment.url.endsWith('/') ? tenant.environment.url : `${tenant.environment.url}/`,
    ).href;

    return { url, token: workroomToken, withBearerTokenAuth };
  }
}

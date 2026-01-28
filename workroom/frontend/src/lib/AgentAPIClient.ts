import { createWorkroomClient, operations } from '@sema4ai/workroom-interface';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { paths as agentServerPaths, operations as AgentServerOperations } from '@sema4ai/agent-server-interface';
import createFetchClient, { ClientMethod, MaybeOptionalInit } from 'openapi-fetch';
import {
  HttpMethod,
  MediaType,
  PathsWithMethod,
  RequiredKeysOf,
  SuccessResponse,
  SuccessResponseJSON,
} from 'openapi-typescript-helpers';
import { UserTenant } from '~/queries/tenants';
import { RequestError } from './Error';
import { getTenantEnvironmentUrl, resolveWorkroomURL } from './utils';
import { getMeta } from './meta';
import { OAuthProvider } from '@sema4ai/oauth-client';

// Reference:
// https://github.com/openapi-ts/openapi-typescript/blob/fdc6d229e995b6009619835530ac74487fda48ef/packages/openapi-fetch/src/index.d.ts#L165
type InitParam<Init> =
  RequiredKeysOf<Init> extends never ? [(Init & { [key: string]: unknown })?] : [Init & { [key: string]: unknown }];

type ApiError = {
  code: string;
  message: string;
  details?: string;
};

type ApiResponse<Success> =
  | {
      data: Success;
      success: true;
    }
  | (ApiError & {
      success: false;
    });

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

type SPAR_upsertDocumentIntelligenceConfigurationPayload = {
  dataConnectionId: string;
  integrations: { type: 'reducto'; api_key: string; endpoint: string }[];
};

// eslint-disable-next-line @typescript-eslint/ban-types
type EmptyObjectType = {};

export type AgentServerConfigType =
  AgentServerOperations['set_config_config__post']['requestBody']['content']['application/json']['config_type'];

export class AgentAPIClient {
  private getUserToken: () => Promise<string | undefined>;
  private workroomToken: WorkroomToken | undefined;
  private tenants: UserTenant[] = [];

  constructor(getUserToken: () => Promise<string | undefined>) {
    this.getUserToken = getUserToken;
  }

  private currentTenantId(): string {
    const pathSegments = window.location.pathname.split('/');
    const tenantIdIndex = pathSegments.indexOf('tenants') + 1;
    const tenantId = pathSegments[tenantIdIndex];

    if (!tenantId) {
      throw new Error('Unable to determine tenant ID from URL');
    }

    return tenantId;
  }

  private async getWorkroomToken() {
    const hasTenantAccess = await this.getTenant(this.currentTenantId());

    if (!hasTenantAccess) {
      const tenants = await this.getTenants();
      throw new RequestError(404, 'Workspace not found', {
        type: 'tenants_selection',
        tenants: tenants.map((tenant) => {
          const tenantWorkroomURL = tenant.environment.tenant_workroom_url ?? `${tenant.environment.url}/${tenant.id}`;

          return {
            name: tenant.name,
            url: tenantWorkroomURL,
          };
        }),
      });
    }

    if (this.workroomToken) {
      const isTokenStillValid = new Date(this.workroomToken.expiresAt).valueOf() - new Date().valueOf() > 60000;
      if (isTokenStillValid) {
        return this.workroomToken.token;
      }
    }

    const metaContent = await getMeta();

    if (metaContent.deploymentType !== undefined) {
      metaContent.deploymentType satisfies 'spar';
      return '_';
    }

    const userToken = await this.getUserToken();

    if (!userToken) {
      throw new RequestError(401, 'Authorization failed');
    }

    const response = await fetch(metaContent.workroomTokenExchangeUrl, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tenantId: this.currentTenantId(),
      }),
    });

    if (!response.ok) {
      throw new RequestError(response.status, 'Authorization failed');
    }

    this.workroomToken = await response.json();

    return this.workroomToken!.token;
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
    const { workroomTenantListUrl } = await getMeta();

    const response = await fetch(workroomTenantListUrl, {
      method: 'GET',
      headers: { authorization: `Bearer ${userToken}` },
    });

    if (!response.ok) {
      throw new RequestError(response.status, 'Authorization failed');
    }

    const tenantsList = ((await response.json()) as { data: UserTenant[] }).data;

    this.tenants = tenantsList;

    return tenantsList;
  }

  public async getAgentMeta({
    agentId,
  }: {
    agentId: string;
  }): Promise<operations['getAgentMeta']['responses'][200]['content']['application/json']> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.currentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/agents/{agentId}/meta', {
      params: {
        path: {
          tenantId: this.currentTenantId(),
          agentId,
        },
      },
    });

    if (response.error) {
      throw new RequestError(response.response.status, response.error.error.message);
    }

    return response.data;
  }

  public async getAgentPermissions({ agentId }: { agentId: string }) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.currentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    try {
      const response = await workroomClient.GET('/tenants/{tenantId}/workroom/agents/{agentId}/me/oauth/permissions', {
        params: {
          path: {
            tenantId: this.currentTenantId(),
            agentId,
          },
          query: {
            redirectUri: `${window.location.protocol}//${window.location.host}/tenants/${this.currentTenantId()}/oauth`,
          },
        },
      });

      if (response.error) {
        return [];
      }

      return response.data as {
        isAuthorized: boolean;
        id: string;
        uri: string;
        providerType: OAuthProvider;
        scopes: string[];
      }[];
    } catch (_) {
      // TODO-V2: This should not silently fail, we should have a flag present whether this endpoint is vene available
      return [];
    }
  }

  public async deleteOAuthConnection({
    agentId,
    connectionId,
  }: {
    agentId: string;
    connectionId: string;
  }): Promise<{ agentId: string; connectionId: string }> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.currentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    const response = await workroomClient.DELETE(
      '/tenants/{tenantId}/workroom/agents/{agentId}/me/oauth/connections/{connectionId}',
      {
        params: {
          path: {
            tenantId: this.currentTenantId(),
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

  public async authorizeOAuth(): Promise<{ success: true } | { success: false; error: { code: string } }> {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.currentTenantId());
    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }
    const params = new URL(document.location.toString()).searchParams;

    // Fix the scope by replacing single slashes with double slashes after 'https:'
    // google will return scope=https:/www... for some reason
    const fixUrlEncoding = (s: string) => s.replace(/https:\/(?!\/)/g, 'https://');
    const scope = fixUrlEncoding(params.get('scope') || '');

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/oauth/authorize', {
      params: {
        path: {
          tenantId: this.currentTenantId(),
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

  public async sendFeedback(payload: { agentId: string; threadId: string; feedback: string; comment: string }) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.currentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    const response = await workroomClient.POST('/tenants/{tenantId}/workroom/feedback', {
      params: {
        path: {
          tenantId: this.currentTenantId(),
        },
      },
      body: payload,
    });

    return !response.error;
  }

  public async listAuditLogs() {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.currentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/audit-logs', {
      params: {
        path: {
          tenantId: this.currentTenantId(),
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
        method: Method,
        path: Path,
        ...init: InitParam<Init>
      ): Promise<ApiResponse<SuccessResponseJSON<Paths[Path][Method]>>> {
        const workroomToken = await this.getWorkroomToken();
        const tenant = await this.getTenant(this.currentTenantId());

        if (!tenant) {
          return {
            success: false,
            code: '404',
            message: 'Workspace not found',
          };
        }

        // Get the environment URL, which does not include the /tenants/<id>
        // portion of the path:
        const environmentUrl = getTenantEnvironmentUrl(tenant);
        // Resolve the full URL so that it includes the /tenants/<id> portion:
        const url = resolveWorkroomURL(pathIdentifier, environmentUrl);

        const client = createFetchClient<Paths>({
          baseUrl: url,
          headers: {
            Authorization: `Bearer ${workroomToken}`,
          },
        });

        const apiResponse = await (
          client[method.toUpperCase() as Uppercase<HttpMethod>] as ClientMethod<EmptyObjectType, Method, MediaType>
        )(
          path as never,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          ...(init as any),
        );

        if (apiResponse.data !== undefined) {
          return {
            success: true,
            data: apiResponse.data as SuccessResponse<Paths[Path][Method]>,
          };
        }

        /**
         * For reponse with 204 status code,
         * we don't receive any data, so we return null
         */
        if (!apiResponse.error && apiResponse.response.status === 204) {
          return {
            success: true,
            data: null as SuccessResponse<Paths[Path][Method]>,
          };
        }

        if (!apiResponse.error) {
          return {
            success: false,
            code: '500',
            message: 'Something went wrong',
          };
        }

        const responseError = apiResponse.error as unknown as { error: ApiError };

        return {
          success: false,
          code: responseError.error.code,
          message: responseError.error.message,
          details: responseError.error.details,
        };
      };
    })<Paths>();
  }

  public get agentFetch() {
    return this.createClient<agentServerPaths>('agents');
  }

  public async startWebsocketStream(agentId: string) {
    const { url, token, withBearerTokenAuth } = await this.getWsStreamUrl({ agentId });
    return withBearerTokenAuth ? new WebSocket(url, ['Bearer', token]) : new WebSocket(url);
  }

  public async startStream({
    args,
  }: {
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
    const tenant = await this.getTenant(this.currentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const { input, thread_id, ...rest } = args;

    const environmentUrl = getTenantEnvironmentUrl(tenant);
    const url = resolveWorkroomURL('agents/api/v2/runs/stream', environmentUrl);

    await fetchEventSource(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${workroomToken}` },
      body: JSON.stringify({ input, thread_id }),
      openWhenHidden: true,
      ...rest,
    });
  }

  private async prepareForRequest() {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.currentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    return { workroomToken, tenant };
  }

  public async getTenantMeta() {
    const { workroomToken } = await this.prepareForRequest();

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    const response = await workroomClient.GET('/tenants/{tenantId}/workroom/meta', {
      params: {
        path: {
          tenantId: this.currentTenantId(),
        },
      },
    });

    if (response.error) {
      // TODO-V2: Should return a failed response and the snackbar should be triggered from the UI
      // errorToast('Unable to fetch Tenant Meta');
      return;
    }

    return response.data;
  }

  public async getActionLogHtml({
    agentId,
    threadId,
    toolCallId,
  }: {
    agentId: string;
    threadId: string;
    toolCallId: string;
  }): Promise<{ success: true; data: { html: string } } | { success: false; error: { message: string } }> {
    const { workroomToken } = await this.prepareForRequest();

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    const getActionLogs = await workroomClient.GET(
      '/tenants/{tenantId}/workroom/agents/{agentId}/threads/{threadId}/action-invocations/{actionInvocationId}',
      {
        params: {
          path: {
            tenantId: this.currentTenantId(),
            agentId,
            threadId,
            actionInvocationId: toolCallId,
          },
        },
        parseAs: 'stream',
      },
    );

    if (![200, 304].includes(getActionLogs.response.status) || !getActionLogs.data) {
      return {
        success: false,
        error: {
          message: getActionLogs.error?.error.message ?? 'Failed to retrieve the action logs',
        },
      };
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

    return { success: true, data: { html: chunks.join('') } };
  }

  /**
   * This method gives URL to connect web socket to the agent server
   * another approach can be creating WebSocket object in this method and
   * return it.
   */
  public async getWsStreamUrl({ agentId }: { agentId: string }) {
    const tenant = await this.getTenant(this.currentTenantId());
    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomToken = await this.getWorkroomToken();

    const withBearerTokenAuth = (await getMeta()).deploymentType !== 'spar';

    const environmentUrl = getTenantEnvironmentUrl(tenant);
    const url = resolveWorkroomURL(`agents/api/v2/runs/${agentId}/stream`, environmentUrl);

    return { url, token: workroomToken, withBearerTokenAuth };
  }

  public async SPAR_upsertDocumentIntelligenceConfiguration({
    configuration,
  }: {
    configuration: {
      documentIntelligenceApiKey: string;
      documentIntelligenceEndpoint: string;
      dataConnectionId: string;
    };
  }): Promise<null> {
    const tenant = await this.getTenant(this.currentTenantId());
    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const workroomToken = await this.getWorkroomToken();

    const environmentUrl = getTenantEnvironmentUrl(tenant);
    const url = resolveWorkroomURL('configure-document-intelligence', environmentUrl);

    const documentIntelligenceConfigResponse = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        authorization: `Bearer ${workroomToken}`,
      },
      body: JSON.stringify({
        dataConnectionId: configuration.dataConnectionId,
        integrations: [
          {
            type: 'reducto',
            api_key: configuration.documentIntelligenceApiKey,
            endpoint: configuration.documentIntelligenceEndpoint,
          },
        ],
      } satisfies SPAR_upsertDocumentIntelligenceConfigurationPayload),
    });

    const documentIntelligenceConfig = (await documentIntelligenceConfigResponse.json()) as null | {
      error: { code: string; message: string };
    };

    if (documentIntelligenceConfig?.error) {
      throw Error(documentIntelligenceConfig.error.message);
    }

    return null;
  }
}

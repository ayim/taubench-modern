import { createWorkroomClient, AgentOAuthPermission, operations } from '@sema4ai/workroom-interface';
import { DocumentIntelligenceSchema } from '@sema4ai/document-intelligence-interface';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import {
  paths as agentServerPaths,
  components as AgentServerComponents,
  operations as AgentServerOperations,
} from '@sema4ai/agent-server-interface';
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

// Reference:
// https://github.com/openapi-ts/openapi-typescript/blob/fdc6d229e995b6009619835530ac74487fda48ef/packages/openapi-fetch/src/index.d.ts#L165
type InitParam<Init> =
  RequiredKeysOf<Init> extends never ? [(Init & { [key: string]: unknown })?] : [Init & { [key: string]: unknown }];

type ApiError = {
  error_id: string;
  code: string;
  message: string;
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
  postgresConnectionUrl: string;
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

  private async getWorkroomToken() {
    if (this.workroomToken) {
      const isTokenStillValid = new Date(this.workroomToken.expiresAt).valueOf() - new Date().valueOf() > 60000;
      if (isTokenStillValid) {
        return this.workroomToken.token;
      }
    }

    const metaContent = await getMeta();

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
    const { workroomTenantListUrl } = await getMeta();

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
      baseUrl: '/',
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
      baseUrl: '/',
      bearerToken: workroomToken,
    });

    try {
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
    } catch (_) {
      // TODO-V2: This should not silently fail, we should have a flag present whether this endpoint is vene available
      return [];
    }
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
      baseUrl: '/',
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
      baseUrl: '/',
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
      baseUrl: '/',
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
      baseUrl: '/',
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
      ): Promise<ApiResponse<SuccessResponseJSON<Paths[Path][Method]>>> {
        const workroomToken = await this.getWorkroomToken();
        const tenant = await this.getTenant(tenantId);

        if (!tenant) {
          return {
            success: false,
            error_id: '404',
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

        // If errorMsg is provided in init argument then show it in toast
        let errorStr = '';

        const errorDetails = init?.[0] ?? null;

        if (errorDetails) {
          errorStr = errorDetails.errorMsg ?? JSON.stringify(apiResponse.error);
          // TODO-V2: Should return a failed response and the snackbar should be triggered from the UI
          // !errorDetails.silent && errorToast(errorDetails.toastMessage ?? errorStr);
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

  public async inspectAgentPackageViaGateway(
    tenantId: string,
    formData: FormData,
  ): Promise<AgentServerComponents['schemas']['StatusResponse_dict_']> {
    const response = await this.agentFetch(tenantId, 'post', '/api/v2/package/inspect/agent', {
      body: formData as never,
    });

    if (!response.success) {
      throw new RequestError(500, response.message);
    }

    return response.data;
  }

  public async deployAgentFromPackage(
    tenantId: string,
    body: AgentServerComponents['schemas']['AgentPackagePayload'],
  ): Promise<AgentServerComponents['schemas']['AgentCompat']> {
    const response = await this.agentFetch(tenantId, 'post', '/api/v2/package/deploy/agent', {
      body: body as never,
    });

    if (!response.success) {
      throw new RequestError(500, response.message);
    }

    return response.data;
  }

  public async updateAgentFromPackage(
    tenantId: string,
    aid: string,
    body: AgentServerComponents['schemas']['AgentPackagePayload'],
  ): Promise<AgentServerComponents['schemas']['AgentCompat']> {
    const response = await this.agentFetch(tenantId, 'put', '/api/v2/package/deploy/agent/{aid}', {
      params: { path: { aid } },
      body: body as never,
    });

    if (!response.success) {
      throw new RequestError(500, response.message);
    }

    return response.data;
  }

  public async deployAgentFromPackageMultipart(
    tenantId: string,
    formData: FormData,
  ): Promise<
    agentServerPaths['/api/v2/package/deploy/agent']['post']['responses']['200']['content']['application/json'] & {
      agent_id: string;
    }
  > {
    const response = await this.agentFetch(tenantId, 'post', '/api/v2/package/deploy/agent', {
      body: formData as never,
    });

    if (!response.success) {
      throw new RequestError(500, response.message);
    }

    if (typeof response.data.agent_id !== 'string') {
      // TODO: should fix the types
      throw new Error('Unexpected: agent ID should always be defined when deploying an agent');
    }

    return {
      ...response.data,
      agent_id: response.data.agent_id,
    };
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

  private async prepareForRequest(tenantId: string) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(tenantId);

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    return { workroomToken, tenant };
  }

  public async getTenantMeta(tenantId: string) {
    const { workroomToken } = await this.prepareForRequest(tenantId);

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
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
      // TODO-V2: Should return a failed response and the snackbar should be triggered from the UI
      // errorToast('Unable to fetch Tenant Meta');
      return;
    }

    return response.data;
  }

  public async getActionLogHtml({
    tenantId,
    agentId,
    threadId,
    toolCallId,
  }: {
    tenantId: string;
    agentId: string;
    threadId: string;
    toolCallId: string;
  }) {
    const { workroomToken } = await this.prepareForRequest(tenantId);

    const workroomClient = createWorkroomClient({
      baseUrl: '/',
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
      // TODO-V2: Should return a failed response and the snackbar should be triggered from the UI
      // errorToast('Unable to fetch Action Log Html');
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

    const withBearerTokenAuth = (await getMeta()).deploymentType !== 'spar';

    const environmentUrl = getTenantEnvironmentUrl(tenant);
    const url = resolveWorkroomURL(`agents/api/v2/runs/${agentId}/stream`, environmentUrl);

    return { url, token: workroomToken, withBearerTokenAuth };
  }

  public async getDocumentIntelligenceConfiguration({
    tenantId,
  }: {
    tenantId: string;
  }): Promise<
    { configured: true } | { configured: false; error: { error_id?: string; code: string; message: string } }
  > {
    try {
      await this.agentFetch(tenantId, 'get', '/api/v2/document-intelligence/ok');

      return { configured: true };
    } catch (e) {
      const error = e as Error;
      return {
        configured: false,
        error: {
          code: 'unexpected_error',
          message: `${error.name}:${error.message}`,
        },
      };
    }
  }

  public async clearDocumentIntelligenceConfiguration({ tenantId }: { tenantId: string }): Promise<{ deleted: true }> {
    await this.agentFetch(tenantId, 'delete', '/api/v2/document-intelligence');

    return { deleted: true };
  }

  public async SPAR_upsertDocumentIntelligenceConfiguration({
    tenantId,
    configuration,
  }: {
    tenantId: string;
    configuration: {
      reductoApiKey: string;
      reductoEndpoint: string;
      postgresConnectionUrl: string;
    };
  }): Promise<null> {
    const tenant = await this.getTenant(tenantId);
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
        postgresConnectionUrl: configuration.postgresConnectionUrl,
        integrations: [
          { type: 'reducto', api_key: configuration.reductoApiKey, endpoint: configuration.reductoEndpoint },
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

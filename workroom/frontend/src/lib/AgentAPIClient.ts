/* eslint-disable class-methods-use-this */
/* eslint-disable @typescript-eslint/no-unused-vars */
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { OAuthProvider } from '@sema4ai/oauth-client';
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

  private tenantId: string | undefined;

  constructor(getUserToken: () => Promise<string | undefined>) {
    this.getUserToken = getUserToken;
  }

  private getCurrentTenantId(): string {
    if (this.tenantId) {
      return this.tenantId;
    }

    const metaEl = document.head.querySelector('meta[name=tenantId]');

    if (!metaEl) {
      throw new Error('No meta for tenantId found in document');
    }

    this.tenantId = metaEl.getAttribute('content') as string;

    return this.tenantId;
  }

  private async getWorkroomToken() {
    const hasTenantAccess = await this.getTenant(this.getCurrentTenantId());

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
        tenantId: this.getCurrentTenantId(),
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

  public async getAgentPermissions(_params: {
    agentId: string;
  }): Promise<{ isAuthorized: boolean; id: string; uri: string; providerType: OAuthProvider; scopes: string[] }[]> {
    return [];
  }

  public async deleteOAuthConnection(_params: {
    agentId: string;
    connectionId: string;
  }): Promise<{ agentId: string; connectionId: string }> {
    throw new Error('OAuth connection management not supported in Moonraker');
  }

  public async authorizeOAuth(): Promise<{ success: true } | { success: false; error: { code: string } }> {
    throw new Error('OAuth authorization not supported in Moonraker');
  }

  public async sendFeedback(_params: {
    agentId: string;
    threadId: string;
    feedback: string;
    comment: string;
  }): Promise<boolean> {
    throw new Error('Feedback not supported in Moonraker');
  }

  // eslint-disable-next-line class-methods-use-this
  private createClient<Paths extends EmptyObjectType>(pathIdentifier: string) {
    // eslint-disable-next-line func-names, @typescript-eslint/no-shadow
    return (function <Paths extends Record<string, Record<HttpMethod, EmptyObjectType>>>() {
      // eslint-disable-next-line func-names
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
        const tenant = await this.getTenant(this.getCurrentTenantId());

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
      threadId: string;
      onmessage?: (event: unknown) => void;
      onopen?: (response: Response) => Promise<void>;
      onclose?: () => void;
      onerror?: (error: Error) => void;
    };
  }) {
    const workroomToken = await this.getWorkroomToken();
    const tenant = await this.getTenant(this.getCurrentTenantId());

    if (!tenant) {
      throw new RequestError(404, 'Workspace not found');
    }

    const { input, threadId, ...rest } = args;

    const environmentUrl = getTenantEnvironmentUrl(tenant);
    const url = resolveWorkroomURL('agents/api/v2/runs/stream', environmentUrl);

    await fetchEventSource(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${workroomToken}` },
      body: JSON.stringify({ input, thread_id: threadId }),
      openWhenHidden: true,
      ...rest,
    });
  }

  public async getActionLogHtml(_params: {
    agentId: string;
    threadId: string;
    toolCallId: string;
  }): Promise<{ success: true; data: { html: string } } | { success: false; error: { message: string } }> {
    throw new Error('Action log HTML not supported in Moonraker');
  }

  /**
   * This method gives URL to connect web socket to the agent server
   * another approach can be creating WebSocket object in this method and
   * return it.
   */
  public async getWsStreamUrl({ agentId }: { agentId: string }) {
    const tenant = await this.getTenant(this.getCurrentTenantId());
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
    };
  }): Promise<null> {
    const tenant = await this.getTenant(this.getCurrentTenantId());
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

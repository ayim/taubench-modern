import { components as AgentServerComponents } from '@sema4ai/agent-server-interface';
import { SparAPIClient } from '../api';
import { createSparMutation, QueryError, ResourceType } from './shared';

// TODO: As of agent-server-interface 2.1.16, the response of the agent package inspection is not typed, so we need to add the typing here.
interface ActionSecretDefinition {
  type: string;
  description?: string;
}

interface AgentPackageAction {
  name: string;
  description: string;
  summary: string;
  operation_kind?: string;
}

interface ActionSecretsMap {
  action: string;
  actionPackage: string;
  secrets: Record<string, ActionSecretDefinition>;
}

interface ExternalEndpointRule {
  host: string;
  port: number;
}

interface ExternalEndpoint {
  name: string;
  description: string;
  'additional-info-link': string;
  rules: ExternalEndpointRule[];
}

export interface AgentActionPackage {
  name: string;
  description: string;
  action_package_version: string;
  actions?: AgentPackageAction[];
  secrets?: Record<string, ActionSecretsMap>;
  'external-endpoints'?: ExternalEndpoint[];
  whitelist?: string;
  whitelistArray?: string[] | null;
  icon?: string;
  path?: string;
}

interface AgentMcpServer {
  name: string;
  transport: 'sse' | 'streamable-http' | 'auto' | 'stdio';
  url: string;
  type: 'generic_mcp' | 'sema4ai_action_server';
  headers: Record<string, unknown>;
}

interface AgentPackageMetadata {
  mode: 'worker' | 'conversational';
}

interface AgentDataSource {
  engine: string;
  customer_facing_name: string;
}

interface AgentLLMModel {
  provider: 'OpenAI';
  name: string;
}

interface UploadedPackageMetadata {
  content_type: string;
  size: number;
  format: string;
}

interface AgentPackageInspectionData {
  name: string;
  description: string;
  version: string;
  icon: string;
  release_note: string;
  metadata: AgentPackageMetadata;
  mcp_servers: AgentMcpServer[];
  action_packages: AgentActionPackage[];
  datasources: AgentDataSource[];
  knowledge: unknown[];
  model: AgentLLMModel;
  architecture: string;
  reasoning: string;
  docker_mcp_gateway: unknown | null;
  docker_mcp_gateway_changes: Record<string, unknown>;
  agent_settings: unknown | null;
  document_intelligence: unknown | null;
  uploaded_package?: UploadedPackageMetadata;
}

type AgentPackageInspectionResponse = Omit<AgentServerComponents['schemas']['StatusResponse_dict_'], 'data'> & {
  data: AgentPackageInspectionData | null;
};

function parseAgentPackageInspectionResponse(response: AgentPackageInspectionResponse): AgentPackageInspectionData {
  if (response.status === 'failure' || !response.data) {
    const errorMessage = response.errors?.[0];
    const message = typeof errorMessage === 'string' ? errorMessage : errorMessage?.message;
    throw new Error(message || 'Failed to inspect agent package');
  }

  const { data } = response;

  const normalizedActionPackages: AgentActionPackage[] = data.action_packages.map((pkg) => ({
    ...pkg,
    description: pkg.description || '',
    actions: pkg.actions || [],
    whitelistArray: pkg.whitelist
      ? pkg.whitelist
          .split(',')
          .map((name) => name.trim())
          .filter(Boolean)
      : null,
  }));

  const normalizedMcpServers: AgentMcpServer[] = (data.mcp_servers || []).map((srv) => ({
    ...srv,
    name: srv.name || '',
    type: (srv.type || 'generic_mcp') as 'generic_mcp' | 'sema4ai_action_server',
    url: srv.url || '',
    transport: (srv.transport === 'sse' || srv.transport === 'streamable-http' ? srv.transport : 'streamable-http') as
      | 'sse'
      | 'streamable-http'
      | 'auto'
      | 'stdio',
    headers: srv.headers || {},
  }));

  const normalizedDatasources: AgentDataSource[] = (data.datasources || []).map((ds) => ({
    ...ds,
    engine: ds.engine || 'unknown',
    customer_facing_name: ds.customer_facing_name || 'Datasource',
  }));

  const normalizedMetadata: AgentPackageMetadata = {
    ...data.metadata,
    mode: data.metadata?.mode === 'worker' ? 'worker' : 'conversational',
  };

  return {
    ...data,
    description: data.description || '',
    action_packages: normalizedActionPackages,
    mcp_servers: normalizedMcpServers,
    datasources: normalizedDatasources,
    metadata: normalizedMetadata,
  };
}

// export const useInspectAgentPackageMutation = () => {
//   const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

//   return useMutation({
//     mutationFn: async ({
//       tenantId,
//       formData,
//     }: {
//       tenantId: string;
//       formData: FormData;
//     }): Promise<AgentPackageInspectionData> => {
//       const response = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/package/inspect/agent', {
//         body: formData as never,
//       });

//       if (!response.success) {
//         throw new RequestError(500, response.message);
//       }

//       const inspectionResponse = response.data as AgentPackageInspectionResponse;
//       return parseAgentPackageInspectionResponse(inspectionResponse);
//     },
//   });
// };

export const useInspectAgentPackageMutation = createSparMutation<
  { sparAPIClient: SparAPIClient },
  { formData: FormData }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ formData }): Promise<AgentPackageInspectionData> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/package/inspect/agent', {
      params: {},
      body: formData as never,
    });
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Agent });
    }
    return parseAgentPackageInspectionResponse(response.data as AgentPackageInspectionResponse);
  },
}));

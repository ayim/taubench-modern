import type { Configuration } from '../configuration.js';
import type { AgentAPIRoute } from './parsers.js';
import type { Permission } from '../auth/permissions.js';
import type { Result } from '../utils/result.js';
import { signAgentToken, type SignAgentTokenErrorOutcome } from '../utils/signing.js';

export type RouteBehaviour =
  | {
      isAllowed: true;
      permissions: Array<Permission>;
      signAgentToken: () => SignAgentTokenResult;
    }
  | {
      isAllowed: false;
    };

type SignAgentTokenResult = Promise<
  Result<
    string,
    | SignAgentTokenErrorOutcome
    | {
        code: 'invalid_signing_auth_configuration';
        message: string;
      }
  >
>;

const ALLOWED = true;
const DISALLOWED = false;

const SIGN_WITH_TENANT = 'tenant';
const SIGN_WITH_USER = 'user';

function getRouteMap(): {
  [Key in AgentAPIRoute['type']]:
    | [isAllowed: false]
    | [isAllowed: true, signMode: 'user' | 'tenant', permissions: Array<Permission>];
} {
  const agentReadPermissions = ['agents.read'] satisfies [Permission];
  const agentWritePermissions = ['agents.write'] satisfies [Permission];
  const deploymentMonitoringReadPermissions = ['deployments_monitoring.read'] satisfies [Permission];

  return {
    // Allowed routes with tenant-level signing
    'get /api/v2/agents/{aid}/files': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/agents/{aid}': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/agents/': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/scenarios': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'delete /api/v2/evals/scenarios/{scenario_id}': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/scenarios/{scenario_id}': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/scenarios/{scenario_id}/runs': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/scenarios/{scenario_id}/runs/latest': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/scenarios/export': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/scenarios/{scenario_id}/runs/{scenario_run_id}': [
      ALLOWED,
      SIGN_WITH_TENANT,
      agentReadPermissions,
    ],
    'delete /api/v2/evals/agents/{agent_id}/batches/{batch_run_id}': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'patch /api/v2/evals/scenarios/{scenario_id}': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/agents/{agent_id}/batches/latest': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'get /api/v2/evals/agents/{agent_id}/batches/{batch_run_id}': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'post /api/v2/evals/agents/{agent_id}/batches': [ALLOWED, SIGN_WITH_TENANT, agentReadPermissions],
    'post /api/v2/package/deploy/agent': [ALLOWED, SIGN_WITH_TENANT, agentWritePermissions],
    'post /api/v2/package/create': [ALLOWED, SIGN_WITH_TENANT, agentWritePermissions],
    'post /api/v2/package/read': [ALLOWED, SIGN_WITH_TENANT, agentWritePermissions],
    'post /api/v2/package/build': [ALLOWED, SIGN_WITH_TENANT, agentWritePermissions],

    // Allowed routes with user-level signing
    'delete /api/v2/threads/{tid}/files': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'delete /api/v2/threads/{tid}/files/{file_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/threads/{tid}/files/request-upload': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/threads/{tid}/files/confirm-upload': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/runs/{run_id}/messages': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/threads/{tid}/messages': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/threads/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/threads/{tid}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'delete /api/v2/threads/{tid}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'patch /api/v2/threads/{tid}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/threads/{tid}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/threads/{tid}/files': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/{tid}/files': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/threads/{tid}/context-stats': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/threads/{tid}/file-by-ref': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/threads/{tid}/files/download/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/runs/{agent_id}/sync': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/runs/{agent_id}/async': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/threads/{tid}/messages/{message_id}/edit': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'patch /api/v2/threads/{tid}/messages/{message_id}/metadata/ops': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/threads/{tid}/state': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/agents/{aid}/agent-details': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'delete /api/v2/agents/{aid}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/work-items': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/work-items/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/work-items/status': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/work-items/summary': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/work-items/{work_item_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'patch /api/v2/work-items/{work_item_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/work-items': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/work-items/': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/work-items/upload-file': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/work-items/{work_item_id}/cancel': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/work-items/{work_item_id}/complete': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/work-items/{work_item_id}/confirm-file': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/work-items/{work_item_id}/continue': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/work-items/{work_item_id}/restart': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'delete /api/v2/mcp-servers/{mcp_server_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/mcp-servers/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/mcp-servers/{mcp_server_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/mcp-servers/': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/mcp-servers/mcp-servers-hosted': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'put /api/v2/mcp-servers/{mcp_server_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/runs/{run_id}/status': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/runs/{aid}/stream': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/config/': [ALLOWED, SIGN_WITH_USER, deploymentMonitoringReadPermissions],
    'post /api/v2/config/': [ALLOWED, SIGN_WITH_USER, deploymentMonitoringReadPermissions],

    // @TODO: New endpoints, needs perms - needs PRODUCT decision
    'get /api/v2/agents/search/by-metadata': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/agents/{agent_id}/user-interfaces': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'delete /api/v2/document-intelligence/data-models/{model_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'delete /api/v2/platforms/{platform_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/capabilities/platforms': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence/data-models': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence/data-models/{model_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence/layouts': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence/ok': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/platforms/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/platforms/{platform_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/threads/{tid}/data-frames': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/threads/{tid}/inspect-file-as-data-frame': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/capabilities/platforms/{kind}/test': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/data-models': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/data-models/generate': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/documents/extract': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/documents/parse': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/layouts': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/documents/parse/async': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/documents/extract/async': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence/jobs/{job_id}/status': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence/jobs/{job_id}/result': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/documents/ingest': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/layouts/generate': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/package/environment-hash/agent': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/package/inspect/action': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/package/inspect/agent': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/platforms/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/{tid}/data-frames/from-file': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/{tid}/data-frames/from-json': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/document-intelligence/data-models/{model_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/package/deploy/agent/{aid}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/platforms/{platform_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/{tid}/data-frames/from-computation': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'delete /api/v2/document-intelligence': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/document-intelligence/layouts/{layout_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'delete /api/v2/document-intelligence/layouts/{layout_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/document-intelligence/layouts/{layout_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/{tid}/data-frames/slice': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/data-sources/list': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/data-sources/update': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'delete /api/v2/data-sources/{data_source_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/quality-checks/generate': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/quality-checks/execute': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/documents/generate-schema': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/data-models/generate-description': [
      ALLOWED,
      SIGN_WITH_USER,
      agentReadPermissions,
    ],
    'get /api/v2/threads/{tid}/data-frames/{data_frame_name}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/document-intelligence/data-models/modify': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/data-connections/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/data-connections/': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/data-connections/{connection_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'delete /api/v2/data-connections/{connection_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'put /api/v2/data-connections/{connection_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/agents/{aid}/data-connections': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/agents/{aid}/data-connections': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],

    'get /api/v2/observability/integrations': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/observability/integrations': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/observability/integrations/{integration_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/observability/integrations/{integration_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'delete /api/v2/observability/integrations/{integration_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/observability/integrations/{integration_id}/validate': [
      ALLOWED,
      SIGN_WITH_USER,
      agentReadPermissions,
    ],
    'get /api/v2/observability/integrations/{integration_id}/scopes': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/observability/integrations/{integration_id}/scopes': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'delete /api/v2/observability/integrations/{integration_id}/scopes': [
      ALLOWED,
      SIGN_WITH_USER,
      agentWritePermissions,
    ],

    'get /api/v2/semantic-data-models/{semantic_data_model_id}': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/semantic-data-models/{semantic_data_model_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'delete /api/v2/semantic-data-models/{semantic_data_model_id}': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/semantic-data-models/{semantic_data_model_id}/export': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],

    'post /api/v2/semantic-data-models/': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/semantic-data-models/import': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/semantic-data-models/validate': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/data-connections/{connection_id}/inspect': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/data-connections/inspect-file-as-data-connection': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],

    'post /api/v2/threads/{tid}/data-frames/assembly-info': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/{tid}/data-frames/as-validated-query': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/threads/{tid}/data-frames/save-as-validated-query': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/semantic-data-models/verify-verified-query': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],

    'post /api/v2/semantic-data-models/generate': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/agents/{aid}/semantic-data-models': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/agents/{aid}/semantic-data-models': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'get /api/v2/threads/{tid}/semantic-data-models': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'put /api/v2/threads/{tid}/semantic-data-models': [ALLOWED, SIGN_WITH_USER, agentWritePermissions],
    'post /api/v2/threads/{tid}/semantic-data-models/validate': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'get /api/v2/semantic-data-models/': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/evals/scenarios': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/evals/scenarios/import': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/evals/scenarios/{scenario_id}/runs': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'post /api/v2/evals/scenarios/suggest': [ALLOWED, SIGN_WITH_USER, agentReadPermissions],
    'delete /api/v2/evals/scenarios/{scenario_id}/runs/{scenario_run_id}': [
      ALLOWED,
      SIGN_WITH_USER,
      agentReadPermissions,
    ],

    // #region Disallowed Routes
    'get /api/v2/health': [DISALLOWED],
    'get /api/v2/ready': [DISALLOWED],
    'get /api/v2/ok': [DISALLOWED],
    'get /api/v2/metrics': [DISALLOWED],
    'put /api/v2/agents/{aid}': [DISALLOWED],
    'post /api/v2/agents/package': [DISALLOWED],
    'get /api/v2/agents/raw': [DISALLOWED],
    'get /api/v2/agents/{aid}/raw': [DISALLOWED],
    'delete /api/v2/debug/artifacts': [DISALLOWED],
    'get /api/v2/agents/by-name': [DISALLOWED],
    'get /api/v2/capabilities/architectures': [DISALLOWED],
    'get /api/v2/debug/artifacts': [DISALLOWED],
    'get /api/v2/debug/artifacts/search': [DISALLOWED],
    'get /api/v2/debug/artifacts/{aid}': [DISALLOWED],
    'post /api/v2/agents/': [DISALLOWED],
    'patch /api/v2/agents/{aid}': [DISALLOWED],
    'put /api/v2/agents/{aid}/raw': [DISALLOWED],
    'post /api/v2/agents/{aid}/refresh-tools': [DISALLOWED],
    'get /api/v2/debug/tools/report-cache-stats': [DISALLOWED],
    'get /api/v2/debug/tools/invalidate-cache': [DISALLOWED],
    'delete /api/v2/threads/': [DISALLOWED],
    'put /api/v2/agents/package/{aid}': [DISALLOWED],
    'put /api/v2/agents/{aid}/action-server-config': [DISALLOWED],
    'post /api/v2/threads/{tid}/fork': [DISALLOWED],
    'post /api/v2/capabilities/mcp/tools': [DISALLOWED],
    // #endregion
  };
}

export function getRouteBehaviour({
  configuration,
  route,
  tenantId,
  userId,
}: {
  configuration: Configuration;
  route: AgentAPIRoute;
  tenantId: string;
  userId: string;
}): RouteBehaviour {
  const createSigner = (mode: 'tenant' | 'user') => async (): SignAgentTokenResult => {
    if (configuration.auth.type === 'none') {
      return {
        success: false,
        error: {
          code: 'invalid_signing_auth_configuration',
          message: 'Invalid auth configuration for signing: auth type none does not support signing tokens',
        },
      };
    }

    return signAgentToken({
      configuration,
      payload: {
        userId: mode === 'tenant' ? `tenant:${tenantId}` : `tenant:${tenantId}:user:${userId}`,
      },
    });
  };

  const routes = getRouteMap();

  const routeConfig = routes[route.type];
  if (!routeConfig) {
    throw new Error(`Invalid route: Route not supported: ${route.type}`);
  }

  const [isAllowed] = routeConfig;

  if (!isAllowed) {
    return { isAllowed: false };
  }

  const [, signMode, permissions] = routeConfig;

  return {
    isAllowed: true,
    signAgentToken: createSigner(signMode),
    permissions,
  };
}

import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { AgentAPIRoute } from './parsers.js';
import type { Configuration } from '../configuration.js';
import type { Result } from '../utils/result.js';
import { signAgentToken, type SignAgentTokenErrorOutcome } from '../utils/signing.js';

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

export function getRouteBehaviour({
  configuration,
  route,
  userId,
}: {
  configuration: Configuration;
  route: AgentAPIRoute;
  userId: string;
}):
  | {
      isAllowed: true;
      signAgentToken: () => SignAgentTokenResult;
    }
  | {
      isAllowed: false;
    } {
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
        userId:
          mode === 'tenant'
            ? `tenant:${configuration.tenant.tenantId}`
            : `tenant:${configuration.tenant.tenantId}:user:${userId}`,
      },
    });
  };

  switch (route.type) {
    // Allowed routes with tenant-level signing
    case 'get /api/v2/agents/{aid}/files':
    case 'get /api/v2/agents/{aid}':
    case 'get /api/v2/agents/':
      return {
        isAllowed: true,
        signAgentToken: createSigner('tenant'),
      };

    // Allowed routes with user-level signing
    case 'delete /api/v2/threads/{tid}/files':
    case 'delete /api/v2/threads/{tid}/files/{file_id}':
    case 'post /api/v2/threads/{tid}/files/request-upload':
    case 'post /api/v2/threads/{tid}/files/confirm-upload':
    case 'get /api/v2/runs/{run_id}/messages':
    case 'post /api/v2/threads/':
    case 'post /api/v2/threads/{tid}/messages':
    case 'get /api/v2/threads/':
    case 'put /api/v2/threads/{tid}':
    case 'delete /api/v2/threads/{tid}':
    case 'patch /api/v2/threads/{tid}':
    case 'get /api/v2/threads/{tid}':
    case 'get /api/v2/threads/{tid}/files':
    case 'post /api/v2/threads/{tid}/files':
    case 'get /api/v2/threads/{tid}/context-stats':
    case 'get /api/v2/threads/{tid}/file-by-ref':
    case 'get /api/v2/threads/{tid}/files/download/':
    case 'post /api/v2/runs/{agent_id}/sync':
    case 'post /api/v2/runs/{agent_id}/async':
    case 'post /api/v2/threads/{tid}/messages/{message_id}/edit':
    case 'get /api/v2/threads/{tid}/state':
    case 'get /api/v2/agents/{aid}/agent-details':
    case 'get /api/v2/work-items/':
    case 'get /api/v2/work-items/{work_item_id}':
    case 'post /api/v2/work-items/':
    case 'post /api/v2/work-items/upload-file':
    case 'post /api/v2/work-items/{work_item_id}/cancel':
    case 'post /api/v2/work-items/{work_item_id}/complete':
    case 'post /api/v2/work-items/{work_item_id}/confirm-file':
    case 'post /api/v2/work-items/{work_item_id}/continue':
    case 'post /api/v2/work-items/{work_item_id}/restart':
    case 'delete /api/v2/mcp-servers/{mcp_server_id}':
    case 'get /api/v2/mcp-servers/':
    case 'get /api/v2/mcp-servers/{mcp_server_id}':
    case 'post /api/v2/mcp-servers/':
    case 'put /api/v2/mcp-servers/{mcp_server_id}':
    case 'get /api/v2/runs/{run_id}/status':
    case 'get /api/v2/runs/{aid}/stream': // moved from isAllowed: false, tenant
      return {
        isAllowed: true,
        signAgentToken: createSigner('user'),
      };

    // #region Disallowed
    case 'get /api/v2/health':
    case 'get /api/v2/ok':
    case 'get /api/v2/metrics':
    case 'put /api/v2/agents/{aid}':
    case 'delete /api/v2/agents/{aid}':
    case 'post /api/v2/agents/package':
    case 'get /api/v2/agents/raw':
    case 'get /api/v2/agents/{aid}/raw':
    case 'delete /api/v2/debug/artifacts':
    case 'get /api/v2/agents/by-name':
    case 'get /api/v2/capabilities/architectures':
    case 'get /api/v2/capabilities/providers':
    case 'get /api/v2/debug/artifacts':
    case 'get /api/v2/debug/artifacts/search':
    case 'get /api/v2/debug/artifacts/{aid}':
    case 'post /api/v2/agents/':
    case 'patch /api/v2/agents/{aid}':
    case 'post /api/v2/capabilities/providers/{kind}/test':
    case 'put /api/v2/agents/{aid}/raw':
    case 'post /api/v2/agents/{aid}/refresh-tools':
    case 'get /api/v2/debug/tools/report-cache-stats':
    case 'get /api/v2/debug/tools/invalidate-cache':
      return {
        isAllowed: false,
      };

    // Disallowed routes with user-level signing
    case 'delete /api/v2/threads/':
    case 'put /api/v2/agents/package/{aid}':
    case 'put /api/v2/agents/{aid}/action-server-config':
    case 'post /api/v2/threads/{tid}/fork':
    case 'post /api/v2/capabilities/mcp/tools':
      return {
        isAllowed: false,
      };
    // #endregion

    default:
      exhaustiveCheck(route);
  }
}

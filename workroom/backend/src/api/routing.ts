import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { AgentAPIRoute } from './parsers.js';
import type { Configuration } from '../configuration.js';
import type { Result } from '../utils/result.js';
import { signAgentToken, type SigningResult } from '../utils/signing.js';

export function isAllowedRoute(route: AgentAPIRoute): boolean {
  switch (route.type) {
    case 'get /api/v2/agents/{aid}/files':
    case 'get /api/v2/agents/{aid}':
    case 'get /api/v2/threads/':
    case 'get /api/v2/threads/{tid}':
    case 'put /api/v2/threads/{tid}':
    case 'get /api/v2/threads/{tid}/files':
    case 'get /api/v2/agents/':
    case 'post /api/v2/agents/': // @TODO: Move this back to the disallowed routes
    case 'post /api/v2/threads/{tid}/files':
    case 'delete /api/v2/threads/{tid}':
    case 'patch /api/v2/threads/{tid}':
    case 'get /api/v2/threads/{tid}/context-stats':
    case 'get /api/v2/threads/{tid}/file-by-ref':
    case 'get /api/v2/threads/{tid}/state':
    case 'delete /api/v2/threads/{tid}/files':
    case 'delete /api/v2/threads/{tid}/files/{file_id}':
    case 'post /api/v2/threads/{tid}/files/request-upload':
    case 'post /api/v2/threads/{tid}/files/confirm-upload':
    case 'get /api/v2/runs/{run_id}/messages':
    case 'get /api/v2/runs/{run_id}/status':
    case 'post /api/v2/threads/':
    case 'post /api/v2/threads/{tid}/messages':
    case 'post /api/v2/runs/{agent_id}/sync':
    case 'post /api/v2/runs/{agent_id}/async':
    case 'get /api/v2/agents/{aid}/agent-details':
    case 'post /api/v2/threads/{tid}/messages/{message_id}/edit':
    case 'get /api/v2/threads/{tid}/files/download/': {
      return true;
    }
    case 'delete /api/v2/threads/':
    case 'delete /api/v2/debug/artifacts':
    case 'get /api/v2/agents/by-name':
    case 'get /api/v2/capabilities/architectures':
    case 'get /api/v2/capabilities/providers':
    case 'get /api/v2/debug/artifacts':
    case 'get /api/v2/debug/artifacts/search':
    case 'get /api/v2/debug/artifacts/{aid}':
    case 'post /api/v2/capabilities/providers/{kind}/test':
    case 'put /api/v2/agents/{aid}/raw':
    case 'get /api/v2/health':
    case 'get /api/v2/ok':
    case 'get /api/v2/metrics':
    case 'put /api/v2/agents/{aid}':
    case 'post /api/v2/agents/{aid}/refresh-tools':
    case 'get /api/v2/debug/tools/report-cache-stats':
    case 'get /api/v2/debug/tools/invalidate-cache':
    case 'get /api/v2/runs/{aid}/stream':
    case 'post /api/v2/agents/package':
    case 'get /api/v2/agents/raw':
    case 'get /api/v2/agents/{aid}/raw':
    case 'put /api/v2/agents/package/{aid}':
    case 'patch /api/v2/agents/{aid}':
    case 'put /api/v2/agents/{aid}/action-server-config':
    case 'post /api/v2/threads/{tid}/fork':
    case 'delete /api/v2/agents/{aid}':
    case 'post /api/v2/capabilities/mcp/tools':
    case 'get /api/v2/mcp-servers/':
    case 'get /api/v2/mcp-servers/{mcp_server_id}':
    case 'post /api/v2/mcp-servers/':
    case 'delete /api/v2/mcp-servers/{mcp_server_id}':
    case 'put /api/v2/mcp-servers/{mcp_server_id}':
    case 'get /api/v2/work-items/':
    case 'post /api/v2/work-items/':
    case 'get /api/v2/work-items/{work_item_id}':
    case 'post /api/v2/work-items/{work_item_id}/confirm-file':
    case 'post /api/v2/work-items/upload-file':
    case 'post /api/v2/work-items/{work_item_id}/cancel':
    case 'post /api/v2/work-items/{work_item_id}/complete':
    case 'post /api/v2/work-items/{work_item_id}/continue':
    case 'post /api/v2/work-items/{work_item_id}/restart': {
      return false;
    }
    default:
      exhaustiveCheck(route);
  }
}

export async function signAgentServiceJWTBasedOnRoute(
  route: AgentAPIRoute,
  { tenantId, userId }: { tenantId: 'spar'; userId: string },
  configuration: Configuration,
): Promise<Result<SigningResult>> {
  return await (async () => {
    switch (route.type) {
      case 'get /api/v2/health':
      case 'get /api/v2/ok':
      case 'get /api/v2/metrics':
      case 'get /api/v2/agents/{aid}/files':
      case 'get /api/v2/agents/{aid}':
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
      case 'get /api/v2/runs/{aid}/stream':
      case 'get /api/v2/runs/{run_id}/status':
      case 'get /api/v2/agents/':
      case 'get /api/v2/mcp-servers/':
      case 'get /api/v2/mcp-servers/{mcp_server_id}':
      case 'post /api/v2/mcp-servers/':
      case 'delete /api/v2/mcp-servers/{mcp_server_id}':
      case 'put /api/v2/mcp-servers/{mcp_server_id}':
      case 'get /api/v2/work-items/':
      case 'post /api/v2/work-items/':
      case 'get /api/v2/work-items/{work_item_id}':
      case 'post /api/v2/work-items/{work_item_id}/confirm-file':
      case 'post /api/v2/work-items/upload-file':
      case 'post /api/v2/work-items/{work_item_id}/cancel':
      case 'post /api/v2/work-items/{work_item_id}/complete':
      case 'post /api/v2/work-items/{work_item_id}/continue':
      case 'post /api/v2/work-items/{work_item_id}/restart': {
        return {
          success: true,
          data: await signAgentToken({
            configuration,
            payload: {
              userId: `tenant:${tenantId}`,
            },
          }),
        };
      }
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
      case 'delete /api/v2/threads/':
      case 'get /api/v2/threads/{tid}':
      case 'get /api/v2/threads/{tid}/files':
      case 'post /api/v2/threads/{tid}/files':
      case 'get /api/v2/threads/{tid}/context-stats':
      case 'get /api/v2/threads/{tid}/file-by-ref':
      case 'get /api/v2/threads/{tid}/files/download/':
      case 'put /api/v2/agents/package/{aid}':
      case 'put /api/v2/agents/{aid}/action-server-config':
      case 'post /api/v2/threads/{tid}/fork':
      case 'post /api/v2/runs/{agent_id}/sync':
      case 'post /api/v2/runs/{agent_id}/async':
      case 'post /api/v2/threads/{tid}/messages/{message_id}/edit':
      case 'get /api/v2/threads/{tid}/state':
      case 'get /api/v2/agents/{aid}/agent-details':
      case 'post /api/v2/capabilities/mcp/tools': {
        return {
          success: true,
          data: await signAgentToken({
            configuration,
            payload: {
              userId: `tenant:${tenantId}:user:${userId}`,
            },
          }),
        };
      }
      default:
        exhaustiveCheck(route);
    }
  })();
}

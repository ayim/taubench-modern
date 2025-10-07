import type { MCPServer } from './mcpServers';
import type { GetPlatformResponse } from './platforms';
import { PROVIDERS, type Provider } from '../components/platforms/llms/components/llmSchemas';

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for MCP server headers validation
 */
export type MCPServerForEditing = MCPServer & {
  type: 'generic_mcp' | 'sema4ai_action_server';
  transport: 'auto' | 'streamable-http' | 'sse' | 'stdio';
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for MCP server headers validation
 */
export const isValidHeaders = (
  headers: unknown,
): headers is Record<string, string | { type?: string; value?: string } | undefined> | null | undefined => {
  return headers === null || headers === undefined || typeof headers === 'object';
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for MCP server type validation
 */
const isValidMcpServerType = (type: string): type is 'generic_mcp' | 'sema4ai_action_server' => {
  return type === 'generic_mcp' || type === 'sema4ai_action_server';
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for MCP transport validation
 */
const isValidMcpTransport = (transport: string): transport is 'auto' | 'streamable-http' | 'sse' | 'stdio' => {
  return transport === 'auto' || transport === 'streamable-http' || transport === 'sse' || transport === 'stdio';
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for MCP server response validation
 */
const isMcpServerReadyForEditing = (server: MCPServer): server is MCPServerForEditing => {
  return isValidMcpServerType(server.type ?? '') && isValidMcpTransport(server.transport ?? '');
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual transformation
 * Data transformation function for MCP server responses
 */
export const transformMcpServerForEditing = (server: MCPServer): MCPServerForEditing => {
  if (!isMcpServerReadyForEditing(server)) {
    throw new Error(`MCP server ${server.mcp_server_id ?? 'unknown'} has invalid type or transport values`);
  }
  return server;
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Properly typed platform for editing with supported provider constraints
 */
export type PlatformForEditing = GetPlatformResponse & {
  kind: Provider;
  name: NonNullable<GetPlatformResponse['name']>;
  models: NonNullable<GetPlatformResponse['models']>;
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for supported platform providers
 */
export const isSupportedProvider = (provider: string): provider is Provider => {
  return PROVIDERS.some((p) => p === provider);
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for platform editing readiness
 */
const isPlatformReadyForEditing = (platform: GetPlatformResponse): platform is PlatformForEditing => {
  return !!(platform.kind && platform.name && platform.models && isSupportedProvider(platform.kind));
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual transformation
 * Data transformation function for platform responses
 */
export const transformPlatformForEditing = (platform: GetPlatformResponse): PlatformForEditing => {
  if (isPlatformReadyForEditing(platform)) {
    return platform;
  }

  const missingFields = [];
  if (!platform.kind) missingFields.push('kind');
  if (!platform.name) missingFields.push('name');
  if (!platform.models) missingFields.push('models');

  if (platform.kind && !isSupportedProvider(platform.kind)) {
    throw new Error(
      `Platform provider '${platform.kind}' is not supported for editing. Only ${PROVIDERS.join(', ')} are supported.`,
    );
  }

  if (missingFields.length > 0) {
    throw new Error(
      `Platform ${platform.platform_id ?? 'unknown'} missing required fields: ${missingFields.join(', ')}`,
    );
  }

  throw new Error(`Platform ${platform.platform_id ?? 'unknown'} validation failed`);
};

/**
 * @deprecated Use proper typing from agent-server-interface once api_key type is fixed
 * Helper to extract string value from api_key field
 */
export const getApiKeyValue = (apiKey?: unknown): string => {
  if (!apiKey) return '';
  return typeof apiKey === 'string' ? apiKey : '';
};

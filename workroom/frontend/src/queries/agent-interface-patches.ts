import type { GetPlatformResponse } from './platforms';
import { PLATFORMS, type Platform } from '../components/platforms/llms/components/llmSchemas';

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Properly typed platform for editing with supported provider constraints
 */
export type PlatformForEditing = GetPlatformResponse & {
  kind: Platform;
  name: NonNullable<GetPlatformResponse['name']>;
  models: NonNullable<GetPlatformResponse['models']>;
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for supported platform providers
 */
const isSupportedPlatform = (platform: string): platform is Platform => {
  return PLATFORMS.some((p) => p === platform);
};

/**
 * @deprecated Use proper typing from agent-server-interface instead of manual validation
 * Type guard for platform editing readiness
 */
const isPlatformReadyForEditing = (platform: GetPlatformResponse): platform is PlatformForEditing => {
  return !!(platform.kind && platform.name && platform.models && isSupportedPlatform(platform.kind));
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

  if (platform.kind && !isSupportedPlatform(platform.kind)) {
    throw new Error(
      `Platform provider '${platform.kind}' is not supported for editing. Only ${PLATFORMS.join(', ')} are supported.`,
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

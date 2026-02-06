import type { components } from '@sema4ai/agent-server-interface';
import { z } from 'zod';

export const OPENAI_MODEL_VALUES = [
  'openai:gpt-5-2-xhigh',
  'openai:gpt-5-2-high',
  'openai:gpt-5-2-medium',
  'openai:gpt-5-2-low',
  'openai:gpt-5-2-none',
  // We are _removing_ gpt 5.1 here, because we never deployed it e2e
  // And we're flopping 5-1 codex to 5-1 codex max (because why use "non-max" version)
  'openai:gpt-5-1-codex-max-xhigh',
  'openai:gpt-5-1-codex-max-high',
  'openai:gpt-5-1-codex-max-medium',
  'openai:gpt-5-1-codex-max-low',
  'openai:gpt-5-high',
  'openai:gpt-5-medium',
  'openai:gpt-5-low',
  'openai:gpt-5-minimal',
  'openai:o4-mini-high',
  'openai:o3-high',
  'openai:o3-low',
  'openai:gpt-4-1',
  'openai:gpt-4-1-mini',
  'openai:gpt-4o',
] as const;
export const AZURE_MODEL_VALUES = [
  'azure:gpt-5-2-xhigh',
  'azure:gpt-5-2-high',
  'azure:gpt-5-2-medium',
  'azure:gpt-5-2-low',
  'azure:gpt-5-2-none',
  'azure:gpt-5-1-codex-max-xhigh',
  'azure:gpt-5-1-codex-max-high',
  'azure:gpt-5-1-codex-max-medium',
  'azure:gpt-5-1-codex-max-low',
  'azure:gpt-5-high',
  'azure:gpt-5-medium',
  'azure:gpt-5-low',
  'azure:gpt-5-minimal',
  'azure:o4-mini-high',
  'azure:o3-high',
  'azure:o3-low',
  'azure:gpt-4-1',
  'azure:gpt-4-1-mini',
  'azure:gpt-4o',
] as const;
export const AZURE_FOUNDRY_MODEL_VALUES = [
  // Azure Foundry - OpenAI models
  'azure_foundry:openai:gpt-4o',
  'azure_foundry:openai:gpt-4o-mini',
  // Azure Foundry - Anthropic Claude models
  'azure_foundry:anthropic:claude-4-5-opus-thinking-high',
  'azure_foundry:anthropic:claude-4-5-opus-thinking-medium',
  'azure_foundry:anthropic:claude-4-5-opus-thinking-low',
  'azure_foundry:anthropic:claude-4-5-opus',
  'azure_foundry:anthropic:claude-4-5-sonnet-thinking-high',
  'azure_foundry:anthropic:claude-4-5-sonnet-thinking-medium',
  'azure_foundry:anthropic:claude-4-5-sonnet-thinking-low',
  'azure_foundry:anthropic:claude-4-5-sonnet',
  'azure_foundry:anthropic:claude-4-5-haiku-thinking-high',
  'azure_foundry:anthropic:claude-4-5-haiku-thinking-medium',
  'azure_foundry:anthropic:claude-4-5-haiku-thinking-low',
  'azure_foundry:anthropic:claude-4-5-haiku',
] as const;

export type AzureFoundryModelFamily = 'openai' | 'anthropic';

export const getAzureFoundryModelFamily = (value: string): AzureFoundryModelFamily => {
  // Format: azure_foundry:family:model
  const parts = value.split(':');
  if (parts.length === 3 && parts[0] === 'azure_foundry') {
    const family = parts[1];
    if (family === 'openai' || family === 'anthropic') {
      return family;
    }
  }
  throw new Error(`Invalid Azure Foundry model value: ${value}`);
};

export const getAzureFoundryModelId = (value: string): string | undefined => {
  // Format: azure_foundry:family:model
  const parts = value.split(':');
  if (parts.length === 3 && parts[0] === 'azure_foundry') {
    return parts[2];
  }
  return undefined;
};

export const getModelFamilyFromPlatform = (models: Record<string, string[]>): string | undefined => {
  // Check the models object for the family
  if ('anthropic' in models) return 'anthropic';
  if ('openai' in models) return 'openai';
  return undefined;
};

export const BEDROCK_MODEL_VALUES = [
  'bedrock:claude-4-5-opus-thinking-high',
  'bedrock:claude-4-5-opus-thinking-medium',
  'bedrock:claude-4-5-opus-thinking-low',
  'bedrock:claude-4-5-opus',
  'bedrock:claude-4-5-sonnet-thinking-high',
  'bedrock:claude-4-5-sonnet-thinking-medium',
  'bedrock:claude-4-5-sonnet-thinking-low',
  'bedrock:claude-4-5-sonnet',
  'bedrock:claude-4-5-haiku-thinking-high',
  'bedrock:claude-4-5-haiku-thinking-medium',
  'bedrock:claude-4-5-haiku-thinking-low',
  'bedrock:claude-4-5-haiku',
  'bedrock:claude-4-1-opus-thinking-high',
  'bedrock:claude-4-1-opus-thinking-medium',
  'bedrock:claude-4-1-opus-thinking-low',
  'bedrock:claude-4-sonnet-thinking-high',
  'bedrock:claude-4-sonnet-thinking-medium',
  'bedrock:claude-4-sonnet-thinking-low',
  'bedrock:claude-4-opus',
  'bedrock:claude-4-sonnet',
] as const;
export const GROQ_MODEL_VALUES = [
  'groq:llama-4-scout',
  'groq:llama-4-maverick',
  'groq:kimi-k2',
  'groq:gpt-oss-120b',
  'groq:gpt-oss-20b',
] as const;
export const GOOGLE_MODEL_VALUES = [
  'google:gemini-3-pro-high',
  // 'google:gemini-3-pro-medium',
  'google:gemini-3-pro-low',
  'google:gemini-3-flash-high',
  'google:gemini-3-flash-medium',
  'google:gemini-3-flash-low',
  'google:gemini-2-5-pro-high',
  'google:gemini-2-5-pro-medium',
  'google:gemini-2-5-pro-low',
  'google:gemini-2-5-flash-high',
  'google:gemini-2-5-flash-medium',
  'google:gemini-2-5-flash-low',
  'google:gemini-2-5-flash-lite',
] as const;

export const GROQ_MODEL_PROVIDER_MAP = {
  'groq:llama-4-scout': 'meta',
  'groq:llama-4-maverick': 'meta',
  'groq:kimi-k2': 'moonshotai',
  'groq:gpt-oss-120b': 'openai',
  'groq:gpt-oss-20b': 'openai',
} as const satisfies Record<(typeof GROQ_MODEL_VALUES)[number], string>;

export const getGroqProviderForModel = (value: string): string | undefined => {
  if (value in GROQ_MODEL_PROVIDER_MAP) {
    return GROQ_MODEL_PROVIDER_MAP[value as (typeof GROQ_MODEL_VALUES)[number]];
  }
  const key = `groq:${value}` as (typeof GROQ_MODEL_VALUES)[number];
  return GROQ_MODEL_PROVIDER_MAP[key];
};

type AllPlatformParameters =
  | components['schemas']['OpenAIPlatformParameters']
  | components['schemas']['AzureOpenAIPlatformParameters']
  | components['schemas']['AzureFoundryPlatformParameters']
  | components['schemas']['BedrockPlatformParameters']
  | components['schemas']['GroqPlatformParameters']
  | components['schemas']['GooglePlatformParameters'];

export type Platform = Extract<
  AllPlatformParameters['kind'],
  'openai' | 'azure' | 'azure_foundry' | 'bedrock' | 'groq' | 'google'
>;

export type UIPlatform = Platform | 'azure_foundry_ui';

export const PLATFORMS = [
  'openai',
  'azure',
  'azure_foundry',
  'bedrock',
  'groq',
  'google',
] as const satisfies readonly Platform[];

export const UI_PLATFORMS: readonly UIPlatform[] = ['openai', 'azure_foundry_ui', 'bedrock', 'groq', 'google'] as const;

export const UI_PLATFORM_VALUES = [...PLATFORMS, 'azure_foundry_ui'] as const;

export const isPlatformValue = (value: string): value is Platform => {
  return PLATFORMS.includes(value as Platform);
};

/**
 * Parses a model value string and extracts platform, model ID, and provider information.
 * Handles both standard two-segment format (platform:model) and triple-segment format (azure_foundry:family:model).
 */
export const parseModelValue = (
  modelValue: string,
  fallbackPlatform: Platform,
): { platform: Platform; modelId: string; provider: string | null } => {
  const parts = modelValue.split(':');

  // Handle triple-segment format for azure_foundry (azure_foundry:family:model)
  if (parts[0] === 'azure_foundry' && parts.length === 3) {
    return {
      platform: 'azure_foundry',
      modelId: parts[2],
      provider: parts[1], // family (e.g., 'anthropic')
    };
  }

  // Standard two-segment format (platform:model)
  const [platformRaw, modelIdRaw] = parts;
  const platform = isPlatformValue(platformRaw ?? '') ? (platformRaw as Platform) : fallbackPlatform;
  const modelId = modelIdRaw ?? modelValue;

  return { platform, modelId, provider: null };
};

// TODO: [fix-type] Backend returns string | null for fields that are required when editing
const baseLLMSchema = z.object({
  platform: z.enum(UI_PLATFORM_VALUES),
  validateLLM: z.boolean(),
  name: z.string().min(1),
  model: z.string().min(1),
  apiKey: z.string().optional(),
  azure_endpoint_url: z.string().url('Must be a valid URL').nullable().optional(),
  azure_api_version: z.string().nullable().optional(),
  azure_deployment_name: z.string().nullable().optional(),
  azure_foundry_endpoint_url: z.string().nullable().optional(),
  azure_foundry_api_key: z.string().nullable().optional(),
  azure_foundry_deployment_name: z.string().nullable().optional(),
  azure_foundry_api_version: z.string().nullable().optional(),
  aws_access_key_id: z.string().nullable().optional(),
  aws_secret_access_key: z.string().nullable().optional(),
  region_name: z.string().nullable().optional(),
  google_api_key: z.string().nullable().optional(),
  google_cloud_project_id: z.string().nullable().optional(),
  google_cloud_location: z.string().nullable().optional(),
  google_use_vertex_ai: z.boolean().nullable().optional(),
  google_vertex_service_account_json: z.string().nullable().optional(),
});

type BaseLLMFormValues = z.infer<typeof baseLLMSchema>;

const validateGoogleVertexRequirements = (values: BaseLLMFormValues, ctx: z.RefinementCtx) => {
  if (values.platform !== 'google' || !values.google_use_vertex_ai) return;

  if (!values.google_cloud_project_id) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['google_cloud_project_id'],
      message: 'Project ID is required',
    });
  }

  if (!values.google_cloud_location) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['google_cloud_location'],
      message: 'Location is required',
    });
  }

  if (!values.google_vertex_service_account_json) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['google_vertex_service_account_json'],
      message: 'Service account JSON is required',
    });
  }
};

const validateAzureFoundryRequirements = (values: BaseLLMFormValues, ctx: z.RefinementCtx) => {
  if (values.platform !== 'azure_foundry' && values.platform !== 'azure_foundry_ui') return;

  if (!values.azure_foundry_endpoint_url) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['azure_foundry_endpoint_url'],
      message: 'Endpoint URL is required',
    });
  }

  if (!values.azure_foundry_deployment_name) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['azure_foundry_deployment_name'],
      message: 'Deployment name is required',
    });
  }

  if (!values.azure_foundry_api_key) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['azure_foundry_api_key'],
      message: 'API key is required',
    });
  }

  // api_version is required for OpenAI family models
  const modelValue = values.model;
  const parts = modelValue.split(':');
  if (parts[0] === 'azure_foundry' && parts[1] === 'openai' && !values.azure_foundry_api_version) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['azure_foundry_api_version'],
      message: 'API version is required for OpenAI models',
    });
  }
};

export const createOrUpdateLLMFormSchema = baseLLMSchema.superRefine((values, ctx) => {
  if (values.platform === 'openai') {
    if (!values.apiKey) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['apiKey'], message: 'API key is required' });
  }
  if (values.platform === 'azure') {
    if (!values.apiKey) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['apiKey'], message: 'API key is required' });
    if (!values.azure_endpoint_url)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['azure_endpoint_url'], message: 'Required' });
    if (!values.azure_api_version)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['azure_api_version'], message: 'Required' });
    if (!values.azure_deployment_name)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['azure_deployment_name'], message: 'Required' });
  }
  if (values.platform === 'azure_foundry' || values.platform === 'azure_foundry_ui') {
    validateAzureFoundryRequirements(values, ctx);
  }
  if (values.platform === 'bedrock') {
    if (!values.aws_access_key_id)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['aws_access_key_id'], message: 'Required' });
    if (!values.aws_secret_access_key)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['aws_secret_access_key'], message: 'Required' });
    if (!values.region_name) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['region_name'], message: 'Required' });
  }
  if (values.platform === 'groq') {
    if (!values.apiKey) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['apiKey'], message: 'API key is required' });
  }
  if (values.platform === 'google') {
    const usingVertexAI = Boolean(values.google_use_vertex_ai);
    if (!usingVertexAI && !values.google_api_key)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['google_api_key'], message: 'API key is required' });
    validateGoogleVertexRequirements(values, ctx);
  }
});

// TODO: [fix-type] Use strictEditLLMSchema once backend guarantees non-null values for editing
export const editLLMFormSchema = baseLLMSchema.superRefine((values, ctx) => {
  validateGoogleVertexRequirements(values, ctx);
  validateAzureFoundryRequirements(values, ctx);
});

export type CreateOrUpdateLLMFormSchema = z.infer<typeof createOrUpdateLLMFormSchema>;
export type EditLLMFormSchema = z.infer<typeof editLLMFormSchema>;

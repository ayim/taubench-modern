import type { components } from '@sema4ai/agent-server-interface';
import { z } from 'zod';
export const OPENAI_MODEL_VALUES = [
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
export const AZURE_MODEL_VALUES = ['azure:azure-openai-service'] as const;
export const BEDROCK_MODEL_VALUES = [
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
  | components['schemas']['BedrockPlatformParameters']
  | components['schemas']['GroqPlatformParameters'];

export type Platform = Extract<AllPlatformParameters['kind'], 'openai' | 'azure' | 'bedrock' | 'groq'>;

export const PLATFORMS = ['openai', 'azure', 'bedrock', 'groq'] as const satisfies readonly Platform[];

export const isPlatformValue = (value: string): value is Platform => {
  return PLATFORMS.includes(value as Platform);
};
// TODO: [fix-type] Backend returns string | null for fields that are required when editing
const baseLLMSchema = z.object({
  platform: z.enum(PLATFORMS),
  validateLLM: z.boolean(),
  name: z.string().min(1),
  model: z.string().min(1),
  apiKey: z.string().optional(),
  azure_endpoint_url: z.string().url('Must be a valid URL').nullable().optional(),
  azure_api_version: z.string().nullable().optional(),
  azure_deployment_name: z.string().nullable().optional(),
  aws_access_key_id: z.string().nullable().optional(),
  aws_secret_access_key: z.string().nullable().optional(),
  region_name: z.string().nullable().optional(),
});

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
});

// TODO: [fix-type] Use strictEditLLMSchema once backend guarantees non-null values for editing
export const editLLMFormSchema = baseLLMSchema;

export type CreateOrUpdateLLMFormSchema = z.infer<typeof createOrUpdateLLMFormSchema>;
export type EditLLMFormSchema = z.infer<typeof editLLMFormSchema>;

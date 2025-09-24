import { z } from 'zod';
import type { components } from '@sema4ai/agent-server-interface';
export const OPENAI_MODEL_VALUES = [
  'openai:gpt-5-high',
  'openai:gpt-5-medium',
  'openai:gpt-5-low',
  'openai:gpt-5-minimal',
  'openai:o4-mini-high',
  'openai:o3-high',
  'openai:o3-low',
  'openai:gpt-4.1',
  'openai:gpt-4.1-mini',
  'openai:gpt-4o',
  'openai:gpt-4-turbo',
  'openai:gpt-3.5-turbo',
] as const;
export const AZURE_MODEL_VALUES = ['azure:azure-openai-service'] as const;
export const BEDROCK_MODEL_VALUES = [
  'bedrock:claude-4-1-opus-thinking-high',
  'bedrock:claude-4-1-opus-thinking-medium',
  'bedrock:claude-4-1-opus-thinking-low',
  'bedrock:claude-4-sonnet-thinking-high',
  'bedrock:claude-4-sonnet-thinking-medium',
  'bedrock:claude-4-sonnet-thinking-low',
  'bedrock:claude-4-opus',
  'bedrock:claude-4-sonnet',
  'bedrock:claude-3.7-sonnet',
  'bedrock:amazon-bedrock',
] as const;

type AllPlatformParameters =
  | components['schemas']['OpenAIPlatformParameters']
  | components['schemas']['AzureOpenAIPlatformParameters']
  | components['schemas']['BedrockPlatformParameters'];

export type Provider = Extract<AllPlatformParameters['kind'], 'openai' | 'azure' | 'bedrock'>;

export const PROVIDERS = ['openai', 'azure', 'bedrock'] as const satisfies readonly Provider[];

// TODO: [fix-type] Backend returns string | null for fields that are required when editing
const baseLLMSchema = z.object({
  provider: z.enum(PROVIDERS),
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
  if (values.provider === 'openai') {
    if (!values.apiKey) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['apiKey'], message: 'API key is required' });
  }
  if (values.provider === 'azure') {
    if (!values.apiKey) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['apiKey'], message: 'API key is required' });
    if (!values.azure_endpoint_url)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['azure_endpoint_url'], message: 'Required' });
    if (!values.azure_api_version)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['azure_api_version'], message: 'Required' });
    if (!values.azure_deployment_name)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['azure_deployment_name'], message: 'Required' });
  }
  if (values.provider === 'bedrock') {
    if (!values.aws_access_key_id)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['aws_access_key_id'], message: 'Required' });
    if (!values.aws_secret_access_key)
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['aws_secret_access_key'], message: 'Required' });
    if (!values.region_name) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['region_name'], message: 'Required' });
  }
});

// TODO: [fix-type] Use strictEditLLMSchema once backend guarantees non-null values for editing
export const editLLMFormSchema = baseLLMSchema;

export type CreateOrUpdateLLMFormSchema = z.infer<typeof createOrUpdateLLMFormSchema>;
export type EditLLMFormSchema = z.infer<typeof editLLMFormSchema>;

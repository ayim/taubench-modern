import { z } from 'zod';
import type { components } from '@sema4ai/agent-server-interface';
export const OPENAI_MODEL_VALUES = [
  'openai:gpt-3.5-turbo',
  'openai:gpt-4-turbo',
  'openai:gpt-4o',
  'openai:gpt-4.1',
  'openai:gpt-4.1-mini',
  'openai:o3-low',
  'openai:o3-high',
  'openai:o4-mini-high',
] as const;
export const AZURE_MODEL_VALUES = ['azure:azure-openai-service'] as const;
export const BEDROCK_MODEL_VALUES = [
  'bedrock:amazon-bedrock',
  'bedrock:claude-3.7-sonnet',
  'bedrock:claude-4-sonnet',
  'bedrock:claude-4-opus',
] as const;

type AllPlatformParameters =
  | components['schemas']['OpenAIPlatformParameters']
  | components['schemas']['AzureOpenAIPlatformParameters']
  | components['schemas']['BedrockPlatformParameters'];

export type Provider = Extract<AllPlatformParameters['kind'], 'openai' | 'azure' | 'bedrock'>;

export const PROVIDERS = ['openai', 'azure', 'bedrock'] as const satisfies readonly Provider[];

const baseLLMSchema = z.object({
  provider: z.enum(PROVIDERS),
  name: z.string().min(1),
  model: z.union([z.enum(OPENAI_MODEL_VALUES), z.enum(AZURE_MODEL_VALUES), z.enum(BEDROCK_MODEL_VALUES)]),
  apiKey: z.string().optional(),
  azure_endpoint_url: z.string().url('Must be a valid URL').optional(),
  azure_api_version: z.string().optional(),
  azure_deployment_name: z.string().optional(),
  aws_access_key_id: z.string().optional(),
  aws_secret_access_key: z.string().optional(),
  region_name: z.string().optional(),
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

// Relaxed schema for editing (credentials optional; server retains existing secrets)
export const editLLMFormSchema = baseLLMSchema;

export type CreateOrUpdateLLMFormSchema = z.infer<typeof createOrUpdateLLMFormSchema>;
export type EditLLMFormSchema = z.infer<typeof editLLMFormSchema>;

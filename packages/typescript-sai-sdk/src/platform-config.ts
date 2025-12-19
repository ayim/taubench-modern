import { z } from 'zod';

// Base platform config
export const BasePlatformConfigSchema = z.object({
  kind: z.string(),
});

// OpenAI platform config
export const OpenAIPlatformConfigSchema = z.object({
  kind: z.literal('openai'),
  openai_api_key: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'openai': ['gpt-4-1', 'o3-high'] }
});

// Azure platform config
export const AzurePlatformConfigSchema = z.object({
  kind: z.literal('azure'),
  azure_api_key: z.string().optional(),
  azure_endpoint_url: z.string().optional(),
  azure_deployment_name: z.string().optional(),
  azure_api_version: z.string().optional(),
  azure_deployment_name_embeddings: z.string().optional(),
  azure_generated_endpoint_url: z.string().optional(),
  azure_generated_endpoint_url_embeddings: z.string().optional(),
  azure_model_backing_deployment_name: z.string().optional(),
  azure_model_backing_deployment_name_embeddings: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'openai': ['gpt-4-1', 'o3-high'] }
});

// OLLama platform config
export const OLLamaPlatformConfigSchema = z.object({
  kind: z.literal('ollama'),
  ollama_base_url: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'ollama': ['gpt-4-1', 'o3-high'] }
});

// Anthropic platform config
export const AnthropicPlatformConfigSchema = z.object({
  kind: z.literal('anthropic'),
  anthropic_api_key: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'anthropic': ["claude-3-5-sonnet"] }
});

// Snowflake platform config
export const SnowflakePlatformConfigSchema = z.object({
  kind: z.literal('cortex'),
  snowflake_warehouse: z.string().optional(),
  snowflake_schema: z.string().optional(),
  snowflake_role: z.string().optional(),
  snowflake_account: z.string().optional(),
  snowflake_database: z.string().optional(),
  snowflake_host: z.string().optional(),
  snowflake_password: z.string().optional(),
  snowflake_username: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'cortex': ["claude-3-5-sonnet"] }
});

// Bedrock platform config
export const BedrockPlatformConfigSchema = z.object({
  kind: z.literal('bedrock'),
  region_name: z.string().optional(),
  api_version: z.string().optional(),
  use_ssl: z.boolean().optional(),
  verify: z.boolean().optional(),
  endpoint_url: z.string().optional(),
  aws_access_key_id: z.string().optional(),
  aws_secret_access_key: z.string().optional(),
  aws_session_token: z.string().optional(),
  config_params: z.record(z.string(), z.any()).optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'bedrock': ["claude-4-opus"] }
});

// LiteLLM platform config
export const LiteLLMPlatformConfigSchema = z.object({
  kind: z.literal('litellm'),
  litellm_api_key: z.string().optional(),
  litellm_base_url: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'litellm': ['model-1', 'model-2'] }
});

// Google platform config
export const GooglePlatformConfigSchema = z.object({
  kind: z.literal('google'),
  google_api_key: z.string().optional(),
  google_cloud_project_id: z.string().optional(),
  google_cloud_location: z.string().optional(),
  google_use_vertex_ai: z.boolean().optional(),
  google_vertex_service_account_json: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'bedrock': ["claude-4-opus"] }
});

// Groq platform config
export const GroqPlatformConfigSchema = z.object({
  kind: z.literal('groq'),
  groq_api_key: z.string().optional(),
  groq_base_url: z.string().optional(),
  models: z.record(z.string(), z.array(z.string())).optional(), // { 'bedrock': ["claude-4-opus"] }
});

// Reducto platform config
export const ReductoPlatformConfigSchema = z.object({
  kind: z.literal('reducto'),
  reducto_api_url: z.string().optional(),
  reducto_api_key: z.string().optional(),
  delegate_kind: z.string().optional(),
  delegate_api_key: z.string().optional(),
});

// Union of all platform configs
export const PlatformConfigSchema = z.discriminatedUnion('kind', [
  OpenAIPlatformConfigSchema,
  AzurePlatformConfigSchema,
  OLLamaPlatformConfigSchema,
  AnthropicPlatformConfigSchema,
  SnowflakePlatformConfigSchema,
  BedrockPlatformConfigSchema,
  LiteLLMPlatformConfigSchema,
  GooglePlatformConfigSchema,
  GroqPlatformConfigSchema,
  ReductoPlatformConfigSchema,
]);

// Type exports
export type PlatformConfig = z.infer<typeof PlatformConfigSchema>;
export type OpenAIPlatformConfig = z.infer<typeof OpenAIPlatformConfigSchema>;
export type AzurePlatformConfig = z.infer<typeof AzurePlatformConfigSchema>;
export type OLLamaPlatformConfig = z.infer<typeof OLLamaPlatformConfigSchema>;
export type AnthropicPlatformConfig = z.infer<typeof AnthropicPlatformConfigSchema>;
export type SnowflakePlatformConfig = z.infer<typeof SnowflakePlatformConfigSchema>;
export type BedrockPlatformConfig = z.infer<typeof BedrockPlatformConfigSchema>;
export type LiteLLMPlatformConfig = z.infer<typeof LiteLLMPlatformConfigSchema>;
export type GooglePlatformConfig = z.infer<typeof GooglePlatformConfigSchema>;
export type GroqPlatformConfig = z.infer<typeof GroqPlatformConfigSchema>;
export type ReductoPlatformConfig = z.infer<typeof ReductoPlatformConfigSchema>;

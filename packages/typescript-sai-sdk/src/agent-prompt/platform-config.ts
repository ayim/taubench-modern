import { z } from 'zod';

// Base platform config
export const BasePlatformConfigSchema = z.object({
  kind: z.string(),
});

// OpenAI platform config
export const OpenAIPlatformConfigSchema = z.object({
  kind: z.literal('openai'),
  openai_api_key: z.string(),
});

// Google platform config
export const GooglePlatformConfigSchema = z.object({
  kind: z.literal('google'),
  google_api_key: z.string(),
});

// Groq platform config
export const GroqPlatformConfigSchema = z.object({
  kind: z.literal('groq'),
  groq_api_key: z.string(),
});

// Bedrock platform config
export const BedrockPlatformConfigSchema = z.object({
  kind: z.literal('bedrock'),
  aws_access_key_id: z.string(),
  aws_secret_access_key: z.string(),
  region_name: z.string(),
});

// Union of all platform configs
export const PlatformConfigSchema = z.discriminatedUnion('kind', [
  OpenAIPlatformConfigSchema,
  GooglePlatformConfigSchema,
  GroqPlatformConfigSchema,
  BedrockPlatformConfigSchema,
]);

// Type exports
export type PlatformConfig = z.infer<typeof PlatformConfigSchema>;
export type OpenAIPlatformConfig = z.infer<typeof OpenAIPlatformConfigSchema>;
export type GooglePlatformConfig = z.infer<typeof GooglePlatformConfigSchema>;
export type GroqPlatformConfig = z.infer<typeof GroqPlatformConfigSchema>;
export type BedrockPlatformConfig = z.infer<typeof BedrockPlatformConfigSchema>;

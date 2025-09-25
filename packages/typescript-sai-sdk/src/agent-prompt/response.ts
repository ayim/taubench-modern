import { z } from 'zod';
import { ContentSchema } from './content';
import { MessageRoleSchema } from './prompt';

// Usage metrics
export const UsageSchema = z.object({
  input_tokens: z.number(),
  output_tokens: z.number(),
  total_tokens: z.number(),
});

// Metrics
export const MetricsSchema = z
  .object({
    latencyMs: z.number().optional(),
  })
  .catchall(z.any());

// Token metrics for metadata
export const TokenMetricsSchema = z.object({
  thinking_tokens: z.number().optional(),
  modality_tokens: z.record(z.string(), z.number()).optional(),
});

// Metadata
export const MetadataSchema = z
  .object({
    request_id: z.string().optional(),
    http_status_code: z.number().optional(),
    http_headers: z.record(z.string(), z.string()).optional(),
    retry_attempts: z.number().optional(),
    host_id: z.string().nullable().optional(),
    token_metrics: TokenMetricsSchema.optional(),
    sema4ai_metadata: z
      .object({
        platform_name: z.string(),
      })
      .optional(),
  })
  .catchall(z.any());

// Additional response fields
export const AdditionalResponseFieldsSchema = z
  .object({
    trace: z.any().nullable().optional(),
    performanceConfig: z.any().nullable().optional(),
  })
  .catchall(z.any());

// Stop reason
export const StopReasonSchema = z.string().nullable();

// Main prompt response
export const PromptResponseSchema = z.object({
  content: z.array(ContentSchema),
  role: MessageRoleSchema,
  raw_response: z.any().nullable(),
  stop_reason: StopReasonSchema,
  usage: UsageSchema,
  metrics: MetricsSchema,
  metadata: MetadataSchema,
  additional_response_fields: AdditionalResponseFieldsSchema,
});

// JsonPatch operations for streaming
export const JsonPatchOperationSchema = z.discriminatedUnion('op', [
  z.object({
    op: z.literal('add'),
    path: z.string(),
    value: z.any(),
  }),
  z.object({
    op: z.literal('replace'),
    path: z.string(),
    value: z.any(),
  }),
  z.object({
    op: z.literal('remove'),
    path: z.string(),
  }),
  z.object({
    op: z.literal('inc'),
    path: z.string(),
    value: z.number(),
  }),
  z.object({
    op: z.literal('concat_string'),
    path: z.string(),
    value: z.string(),
  }),
]);

// Streaming response event
export const StreamingEventSchema = z.object({
  data: JsonPatchOperationSchema,
});

// Type exports
export type Usage = z.infer<typeof UsageSchema>;
export type Metrics = z.infer<typeof MetricsSchema>;
export type TokenMetrics = z.infer<typeof TokenMetricsSchema>;
export type Metadata = z.infer<typeof MetadataSchema>;
export type AdditionalResponseFields = z.infer<typeof AdditionalResponseFieldsSchema>;
export type StopReason = z.infer<typeof StopReasonSchema>;
export type PromptResponse = z.infer<typeof PromptResponseSchema>;
export type JsonPatchOperation = z.infer<typeof JsonPatchOperationSchema>;
export type StreamingEvent = z.infer<typeof StreamingEventSchema>;

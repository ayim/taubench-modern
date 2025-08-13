import { z } from 'zod';

// Text content
export const TextContentSchema = z.object({
  text: z.string(),
});

// Text content with explicit kind
export const TextContentWithKindSchema = z.object({
  kind: z.literal('text'),
  text: z.string(),
});

// Image content
export const ImageContentSchema = z.object({
  kind: z.literal('image'),
  value: z.string(), // base64 encoded image data
  mime_type: z.string(), // e.g., "image/jpeg", "image/png"
  sub_type: z.literal('base64'),
  detail: z.enum(['low_res', 'high_res']).optional(),
});

// Tool use content
export const ToolUseContentSchema = z.object({
  kind: z.literal('tool_use'),
  tool_name: z.string(),
  tool_call_id: z.string(),
  tool_input_raw: z.string(), // JSON string of tool input
});

// Tool result content
export const ToolResultContentSchema = z.object({
  kind: z.literal('tool_result'),
  tool_name: z.string(),
  tool_call_id: z.string(),
  content: z.array(TextContentSchema), // Currently only text content is supported for tool results
});

// Union of all content types
export const ContentSchema = z.discriminatedUnion('kind', [
  TextContentWithKindSchema,
  ImageContentSchema,
  ToolUseContentSchema,
  ToolResultContentSchema,
]);

// Content that can appear in messages (includes plain text without kind)
export const MessageContentSchema = z.union([TextContentSchema, ContentSchema]);

// Type exports
export type TextContent = z.infer<typeof TextContentSchema>;
export type TextContentWithKind = z.infer<typeof TextContentWithKindSchema>;
export type ImageContent = z.infer<typeof ImageContentSchema>;
export type ToolUseContent = z.infer<typeof ToolUseContentSchema>;
export type ToolResultContent = z.infer<typeof ToolResultContentSchema>;
export type Content = z.infer<typeof ContentSchema>;
export type MessageContent = z.infer<typeof MessageContentSchema>;

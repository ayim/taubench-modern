import { z } from 'zod';
import { MessageContentSchema } from './content';
import { ToolSchema } from './tools';
import { PlatformConfigSchema } from '../platform-config';

// Message roles - extended to support special messages
export const MessageRoleSchema = z.enum(['user', 'agent']);
export const SpecialMessageRoleSchema = z
  .string()
  .refine((role) => role.startsWith('$'), { message: "Special message roles must start with '$'" });

// Special message types
export const ConversationHistorySpecialMessageSchema = z.object({
  role: z.literal('$conversation_history'),
  num_turns: z.number().optional(),
});

export const DocumentsSpecialMessageSchema = z.object({
  role: z.literal('$documents'),
  document_ids: z.array(z.string()).optional(),
});

export const MemoriesSpecialMessageSchema = z.object({
  role: z.literal('$memories'),
  memory_limit: z.number().optional(),
});

// Union of all special messages
export const SpecialMessageSchema = z.discriminatedUnion('role', [
  ConversationHistorySpecialMessageSchema,
  DocumentsSpecialMessageSchema,
  MemoriesSpecialMessageSchema,
]);

// Regular message
export const MessageSchema = z.object({
  role: MessageRoleSchema,
  content: z.array(MessageContentSchema),
});

// Union of all message types (regular + special)
export const AllMessageSchema = z.union([MessageSchema, SpecialMessageSchema]);

// Tool choice - can be "auto", "any", or specific tool name
export const ToolChoiceSchema = z.union([
  z.literal('auto'),
  z.literal('any'),
  z.string(), // specific tool name
]);

// Prompt configuration
export const PromptSchema = z
  .object({
    system_instruction: z.string().optional().nullable(),
    messages: z.array(AllMessageSchema).default([]),
    tools: z.array(ToolSchema).default([]),
    tool_choice: ToolChoiceSchema.default('auto'),
    temperature: z.number().min(0.0).max(1.0).optional().nullable(),
    seed: z.number().int().optional().nullable(),
    max_output_tokens: z.number().positive().optional().nullable(),
    stop_sequences: z.array(z.string()).optional().nullable(),
    top_p: z.number().min(0.0).max(1.0).optional().nullable(),
  })
  .refine(
    (data) => {
      // Validate that tool_choice references a valid tool if it's not 'auto' or 'any'
      if (data.tool_choice !== 'auto' && data.tool_choice !== 'any') {
        const toolNames = data.tools.map((tool) => tool.name);
        if (!toolNames.includes(data.tool_choice)) {
          return false;
        }
      }
      return true;
    },
    {
      message: "Invalid tool choice: must be 'auto', 'any', or the name of a provided tool",
      path: ['tool_choice'],
    },
  );

// Full prompt request
export const PromptRequestSchema = z.object({
  platform_config_raw: PlatformConfigSchema,
  prompt: PromptSchema,
});

// Type exports
export type MessageRole = z.infer<typeof MessageRoleSchema>;
export type SpecialMessageRole = z.infer<typeof SpecialMessageRoleSchema>;
export type ConversationHistorySpecialMessage = z.infer<typeof ConversationHistorySpecialMessageSchema>;
export type DocumentsSpecialMessage = z.infer<typeof DocumentsSpecialMessageSchema>;
export type MemoriesSpecialMessage = z.infer<typeof MemoriesSpecialMessageSchema>;
export type SpecialMessage = z.infer<typeof SpecialMessageSchema>;
export type Message = z.infer<typeof MessageSchema>;
export type AllMessage = z.infer<typeof AllMessageSchema>;
export type ToolChoice = z.infer<typeof ToolChoiceSchema>;
export type Prompt = z.infer<typeof PromptSchema>;
export type PromptRequest = z.infer<typeof PromptRequestSchema>;

import { z } from 'zod';

// JSON Schema for tool input
export const JsonSchemaPropertySchema = z.object({
  type: z.enum(['string', 'number', 'integer', 'boolean', 'array', 'object']),
  description: z.string().optional(),
  enum: z.array(z.any()).optional(),
  items: z.any().optional(), // For array types
  properties: z.record(z.string(), z.any()).optional(), // For object types
  required: z.array(z.string()).optional(),
});

export const JsonSchemaSchema = z.object({
  type: z.literal('object'),
  properties: z.record(z.string(), JsonSchemaPropertySchema),
  required: z.array(z.string()).optional(),
  description: z.string().optional(),
});

// Tool Schema - specifies the tool with its name, description, and input schema
export const ToolSchema = z.object({
  name: z.string(), // Name of the tool - used as identifier for the tool
  description: z.string(), // Description of the tool
  input_schema: JsonSchemaSchema, // Schema for the tool input - used to validate the tool input
  category: z.enum(['internal-tool', 'action-tool', 'mcp-tool', 'client-exec-tool', 'client-info-tool']), // Category of the tool
});

// Type exports
export type JsonSchemaProperty = z.infer<typeof JsonSchemaPropertySchema>;
export type JsonSchema = z.infer<typeof JsonSchemaSchema>;
export type Tool = z.infer<typeof ToolSchema>;

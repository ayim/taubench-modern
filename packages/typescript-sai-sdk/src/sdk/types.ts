import { z } from 'zod';
import { ToolSchema } from '../agent-prompt/tools';

// Context Schema - specifies the context in which the agent operates with parameters
export const ContextSchema = z.object({
  system_instruction: z.string().optional().nullable(),
  temperature: z.number().min(0.0).max(1.0).optional().nullable(),
  seed: z.number().int().optional().nullable(),
  max_output_tokens: z.number().positive().optional().nullable(),
  stop_sequences: z.array(z.string()).optional().nullable(),
  top_p: z.number().min(0.0).max(1.0).optional().nullable(),
});

// Scenario Tool - a tool that can be used in a scenario
export const ScenarioToolSchema = z.object({
  ...ToolSchema.shape,
  callback: z.custom<(input: any) => any>((val) => typeof val === 'function'), // Callback function for the tool
});

// Scenario Schema - specifies the scenario in which the agent operates with parameters
export const ScenarioSchema = z.object({
  name: z.string(), // Name of the scenario - used as identifier for the scenario
  context: ContextSchema, // Context of the scenario
  prompt: z.string(), // Prompt of the scenario - The User message to the Agent
  tools: z.array(ScenarioToolSchema), // Tools of the scenario
  verbose: z.boolean().optional(), // Whether to log verbose output
});

// Type exports
export type Context = z.infer<typeof ContextSchema>;
export type ScenarioTool = z.infer<typeof ScenarioToolSchema>;
export type Scenario = z.infer<typeof ScenarioSchema>;

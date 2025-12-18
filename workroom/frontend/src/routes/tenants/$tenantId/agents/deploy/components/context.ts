import { z } from 'zod';
import { headerEntrySchema, mcpTransportSchema, mcpServerTypeSchema, mcpUrlSchema } from '~/lib/mcpServersUtils';

export enum AgentDeploymentStep {
  AgentOverview = 'AgentOverview',
  AgentSettings = 'AgentSettings',
  ActionSettings = 'ActionSettings',
}

const MCPServerSettingsSchema = z.object({
  name: z.string().min(1),
  type: mcpServerTypeSchema,
  transport: mcpTransportSchema,
  url: mcpUrlSchema,
  headersKV: z.array(headerEntrySchema).default([]),
  command: z.string().nullable().optional(),
  args: z.array(z.string()).nullable().optional(),
  cwd: z.string().nullable().optional(),
  force_serial_tool_calls: z.boolean(),
  mcpServerId: z.string().optional(),
});

export const buildAgentDeploymentSchema = ({ existingAgentNames }: { existingAgentNames: string[] }) => {
  const agentConfigurationSchema = z.object({
    name: z
      .string()
      .min(1)
      .refine(
        (inputedAgentName) => {
          const agentWithSameNameExists = !existingAgentNames.find(
            (existingAgent) => existingAgent === inputedAgentName,
          );
          return agentWithSameNameExists;
        },
        {
          message: 'An agent with this name already exists',
        },
      ),
    description: z.string().min(1),
    llmId: z.string().min(1, 'LLM setting is required'),
    apiKey: z.string().optional(),
  });

  const mcpConfigurationSchema = z.object({
    mcpServerSettings: z.array(MCPServerSettingsSchema).optional(),
    mcpServerIds: z.array(z.string()).optional(),
  });

  return agentConfigurationSchema.and(mcpConfigurationSchema);
};

export type AgentDeploymentFormSchema = z.input<ReturnType<typeof buildAgentDeploymentSchema>>;

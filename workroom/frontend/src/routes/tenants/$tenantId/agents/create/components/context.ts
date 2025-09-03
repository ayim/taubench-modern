import { z } from 'zod';

export enum AgentDeploymentStep {
  AgentOverview = 'AgentOverview',
  AgentSettings = 'AgentSettings',
  ActionSettings = 'ActionSettings',
}

export const buildAgentDeploymentSchema = ({ existingAgentNames }: { existingAgentNames: string[] }) => {
  const MCPVariableTypeStringSchema = z.object({
    type: z.literal('string'),
    description: z.string().nullable().optional(),
    value: z.string().nullable().optional(),
  });
  const MCPVariableTypeSecretSchema = z.object({
    type: z.literal('secret'),
    description: z.string().nullable().optional(),
    value: z.string().nullable().optional(),
  });

  const MCPVarSchema = z.union([MCPVariableTypeStringSchema, MCPVariableTypeSecretSchema]);

  const MCPServerHeaders = z.record(z.string(), MCPVarSchema).nullable();

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

  const MCPServerSettingsSchema = z.object({
    name: z.string().min(1),
    url: z.string().min(1).nullable().optional(),
    transport: z.enum(['auto', 'streamable-http', 'sse', 'stdio']),
    headers: MCPServerHeaders.optional().refine(
      (headers) => {
        if (!headers) return true;
        return Object.keys(headers).every((k) => k.trim().length > 0);
      },
      { path: ['headers'], message: 'Header keys must be non-empty' },
    ),
    command: z.string().nullable().optional(),
    args: z.array(z.string()).nullable().optional(),
    env: z
      .record(z.string(), z.union([z.string(), MCPVarSchema]))
      .nullable()
      .optional(),
    cwd: z.string().nullable().optional(),
    force_serial_tool_calls: z.boolean(),
  });

  const mcpConfigurationSchema = z.object({
    mcpServerSettings: z.array(MCPServerSettingsSchema).optional(),
  });

  return agentConfigurationSchema.and(mcpConfigurationSchema);
};

export type AgentDeploymentFormSchema = z.infer<ReturnType<typeof buildAgentDeploymentSchema>>;
export type MCPServerSettings = NonNullable<AgentDeploymentFormSchema['mcpServerSettings']>[number];
export type MCPHeaderValue =
  | { type: 'string'; description?: string | null; value?: string | null }
  | { type: 'secret'; description?: string | null; value?: string | null };

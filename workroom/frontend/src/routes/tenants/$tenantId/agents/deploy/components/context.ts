import { z } from 'zod';

export enum AgentDeploymentStep {
  AgentOverview = 'AgentOverview',
  AgentSettings = 'AgentSettings',
  ActionSettings = 'ActionSettings',
}

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
    mcpServerIds: z.array(z.string()).optional(),
  });

  return agentConfigurationSchema.and(mcpConfigurationSchema);
};

export type AgentDeploymentFormSchema = z.input<ReturnType<typeof buildAgentDeploymentSchema>>;

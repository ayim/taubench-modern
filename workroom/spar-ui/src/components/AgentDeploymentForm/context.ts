import { FC } from 'react';
import { z } from 'zod';

import { AgentPackageInspectionResponse } from '../../queries';

export type AgentDeploymentFormSection = FC<{
  agentTemplate: NonNullable<AgentPackageInspectionResponse>;
}>;

export const buildAgentDeploymentSchema = ({ existingAgentNames }: { existingAgentNames: string[] }) => {
  const agentConfigurationSchema = z.object({
    name: z
      .string()
      .trim()
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
    description: z.string().trim().min(1),
    llmId: z.string().min(1, 'LLM setting is required'),
    apiKey: z.string().optional(),
  });

  const mcpConfigurationSchema = z.object({
    mcpServerIds: z.array(z.string()).optional(),
    // Per-server secrets: { [serverId]: { [secretName]: secretValue } }
    mcpServerSecrets: z.record(z.string(), z.record(z.string(), z.string())).optional(),
    // Secrets for the agent package's action packages: { [secretName]: secretValue }
    agentPackageSecrets: z.record(z.string(), z.string()).optional(),
  });

  return agentConfigurationSchema.and(mcpConfigurationSchema);
};

export const getDefaultValues = (agentTemplate: NonNullable<AgentPackageInspectionResponse>) => {
  return {
    name: agentTemplate.name,
    description: agentTemplate.description,
    llmId: '',
    apiKey: '',
    mcpServerIds: [],
  };
};

export type AgentDeploymentFormSchema = z.input<ReturnType<typeof buildAgentDeploymentSchema>>;

import { z } from 'zod';
import type { components } from '@sema4ai/agent-server-interface';
import type { useAgentQuery } from '~/queries/agents';

type Agent = NonNullable<ReturnType<typeof useAgentQuery>['data']>;
type UpsertAgentPayload = components['schemas']['UpsertAgentPayload'];

type ZodSubset<T> = {
  [K in keyof T]?: z.ZodType<T[K]>;
};

export type AgentDetailsSchema = z.infer<typeof AgentDetailsSchema>;

export const AgentDetailsSchema = z.object({
  name: z.string().trim().min(1),
  version: z.string().trim().min(1),
  description: z.string().trim(),
  public: z.boolean(),
  mode: z.enum(['conversational', 'worker']),
  runbook: z.string().optional(),
  agent_architecture: z.object({
    name: z.string().trim().min(1),
    version: z.string().trim().min(1),
  }),
  extra: z
    .object({
      conversation_starter: z.string().optional(),
    })
    .optional(),
  platform_params_ids: z.array(z.string()),
  mcp_server_ids: z.array(z.string()),
  document_intelligence: z.enum(['v2', 'v2.1']),
} satisfies ZodSubset<UpsertAgentPayload>);

export const getDefaultValues = (agent: Agent): AgentDetailsSchema => ({
  name: agent.name,
  version: agent.version,
  mode: agent.mode,
  public: agent.public,
  description: agent.description,
  agent_architecture: {
    name: agent.agent_architecture.name,
    version: agent.agent_architecture.version,
  },
  platform_params_ids: agent.platform_params_ids || [],
  mcp_server_ids: agent.mcp_server_ids || [],
  document_intelligence: 'v2.1',
  ...(agent.extra ? { extra: agent.extra } : {}),
});

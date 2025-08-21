import { z } from 'zod';

const headerValueSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('string'),
    value: z.string(),
  }),
  z.object({
    type: z.literal('secret'),
    secretID: z.string(),
  }),
]);

const headerValueOAuth2SecretSchema = z.object({
  type: z.literal('oauth2-secret'),
  provider: z.string(),
  scopes: z.array(z.string()),
  value: headerValueSchema,
  description: z.string().nullable(),
});

const headerValueStringWithDefaultSchema = z.object({
  type: z.literal('string'),
  value: headerValueSchema,
  description: z.string().nullable(),
});

const headerValueSecretSchema = z.object({
  type: z.literal('secret'),
  value: headerValueSchema,
  description: z.string().nullable(),
});

const headerTypeSchema = z.union([
  headerValueOAuth2SecretSchema,
  headerValueStringWithDefaultSchema,
  headerValueSecretSchema,
]);

export type MCPServerHeaders = z.infer<typeof MCPServerHeaders>;
const MCPServerHeaders = z.record(z.string(), headerTypeSchema).nullable();

export const AgentDeploymentFormSchemaStep1Schema = z.object({
  agentTemplateId: z.string(),
  actionDeploymentIds: z.array(z.string()),
  actionIds: z.array(z.string()),
  updateDeploymentId: z.string().optional(),
});

export const AgentDeploymentFormSchemaStep2Schema = z.object({
  name: z.string().min(1),
  description: z.string().min(1),
  workspaceId: z.string().optional(), // Made optional since we removed workspace selector
  llmId: z.string().min(1, 'LLM setting is required'),
  apiKey: z.string().min(1, 'API key is required'),
  oAuthProviders: z.record(z.string(), z.string().min(1)).optional(),
  feedbackRecipients: z
    .array(
      z.object({
        firstName: z.string().min(1).max(100),
        lastName: z.string().min(1).max(100),
        email: z.string().email().min(1).max(100),
      }),
    )
    .max(5)
    .optional(),
  langsmithIntegrationId: z.string().min(1).optional(),
});

export type MCPServerSettings = z.infer<typeof MCPServerSettings>;
export const MCPServerSettings = z.object({
  name: z.string().min(1),
  url: z.string().min(1),
  transport: z.enum(['auto', 'streamable-http', 'sse', 'stdio']),
  headers: MCPServerHeaders,
});

export const AgentDeploymentFormSchemaStep3Schema = z.object({
  actionSettings: z.record(
    z.string(),
    z
      .object({
        secretId: z.string(),
      })
      .or(z.object({ value: z.string().min(1) }))
      .refine(
        (secretDetails) => 'value' in secretDetails || 'secretId' in secretDetails,
        'Enter a secret value or choose a Secret',
      ),
  ),
  mcpServerSettings: z.array(MCPServerSettings).optional(),
});

export const AgentDeploymentFormSchemaStep4Schema = z.object({
  documentWorkflowAssignment: z
    .object({
      documentName: z.string(),
      stageId: z.string(),
    })
    .nullable(),
});

export const AgentDeploymentFormSchemaStep5Schema = z.object({
  dataSources: z
    .object({ agentTemplateDataSourceId: z.string(), dataSourceConnectionId: z.string().min(1) })
    .array()
    .default([]),
});

export enum AgentDeploymentStep {
  AgentOverview = 'AgentOverview',
  AgentSettings = 'AgentSettings',
  ActionSettings = 'ActionSettings',
  Triggers = 'Triggers',
  DataSources = 'DataSources',
}

export type AgentDeploymentFormStep1 = z.infer<typeof AgentDeploymentFormSchemaStep1Schema>;
export type AgentDeploymentFormStep2 = z.infer<typeof AgentDeploymentFormSchemaStep2Schema>;
export type AgentDeploymentFormStep3 = z.infer<typeof AgentDeploymentFormSchemaStep3Schema>;
export type AgentDeploymentFormStep4 = z.infer<typeof AgentDeploymentFormSchemaStep4Schema>;
export type AgentDeploymentFormStep5 = z.infer<typeof AgentDeploymentFormSchemaStep5Schema>;

export const AgentDeploymentFormValidators: Record<AgentDeploymentStep, z.ZodSchema> = {
  AgentOverview: AgentDeploymentFormSchemaStep1Schema,
  AgentSettings: AgentDeploymentFormSchemaStep2Schema,
  ActionSettings: AgentDeploymentFormSchemaStep3Schema,
  Triggers: AgentDeploymentFormSchemaStep4Schema,
  DataSources: AgentDeploymentFormSchemaStep5Schema,
};

export type AgentDeploymentFormSchema = AgentDeploymentFormStep1 &
  AgentDeploymentFormStep2 &
  AgentDeploymentFormStep3 &
  AgentDeploymentFormStep4 &
  AgentDeploymentFormStep5;

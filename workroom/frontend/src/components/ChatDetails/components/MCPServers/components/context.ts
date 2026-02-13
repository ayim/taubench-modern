import z from 'zod';

export const MCPConfigurationSchema = z.object({
  mcp_server_ids: z.array(z.string()),
});

export type MCPConfigurationSchema = z.infer<typeof MCPConfigurationSchema>;

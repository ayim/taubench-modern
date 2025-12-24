import { z } from 'zod';
import { ServerResponse } from '../../../queries/shared';

/**
 * MCP Authentication Schemas
 *
 * OAuth2 authentication types following RFC 6749 terminology:
 * - Client Credentials Flow (Section 4.4) - for M2M authentication
 * - Authorization Code Flow (Section 4.1) - for user authentication
 *
 * @see https://datatracker.ietf.org/doc/html/rfc6749
 */

export const mcpAuthenticationTypeSchema = z.enum(['none', 'oauth2-client-credentials', 'oauth2-authorization-code']);
export type MCPAuthenticationType = z.infer<typeof mcpAuthenticationTypeSchema>;

export const mcpAuthenticationTypeSelectItems: { value: MCPAuthenticationType; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'oauth2-client-credentials', label: 'OAuth2 Client Credentials' },
  { value: 'oauth2-authorization-code', label: 'OAuth2 Authorization Code' },
];

export const mcpClientCredentialsSchema = z.object({
  endpoint: z.string().min(1, 'Endpoint is required').url('Endpoint must be a valid URL'),
  client_id: z.string().min(1, 'Client ID is required'),
  client_secret: z.string().min(1, 'Client Secret is required'),
  scope: z.string().optional(),
});
export type MCPClientCredentials = z.infer<typeof mcpClientCredentialsSchema>;

export const mcpClientCredentialsPartialSchema = z.object({
  endpoint: z.string().optional(),
  client_id: z.string().optional(),
  client_secret: z.string().optional(),
  scope: z.string().optional(),
});
export type MCPClientCredentialsPartial = z.infer<typeof mcpClientCredentialsPartialSchema>;

/**
 * Authentication metadata - matches backend AuthenticationMetadataM2M
 */
export const mcpAuthenticationMetadataSchema = z.object({
  endpoint: z.string(),
  client_id: z.string(),
  client_secret: z.string(),
  scope: z.string(),
});
export type MCPAuthenticationMetadata = z.infer<typeof mcpAuthenticationMetadataSchema>;

export const mcpAuthenticationFormSchema = z.object({
  authentication_type: mcpAuthenticationTypeSchema.default('none'),
  client_credentials: mcpClientCredentialsSchema.optional(),
});

export function refineClientCredentials(
  data: { authentication_type: string; client_credentials?: MCPClientCredentialsPartial },
  ctx: z.RefinementCtx,
) {
  if (data.authentication_type !== 'oauth2-client-credentials') {
    return;
  }

  const creds = data.client_credentials;

  const endpoint = creds?.endpoint?.trim();
  if (!endpoint) {
    ctx.addIssue({
      path: ['client_credentials', 'endpoint'],
      code: 'custom',
      message: 'Endpoint is required for OAuth2 Client Credentials Flow',
    });
  } else if (!URL.canParse(endpoint)) {
    ctx.addIssue({
      path: ['client_credentials', 'endpoint'],
      code: 'custom',
      message: 'Endpoint must be a valid URL',
    });
  }

  if (!creds?.client_id?.trim()) {
    ctx.addIssue({
      path: ['client_credentials', 'client_id'],
      code: 'custom',
      message: 'Client ID is required for OAuth2 Client Credentials Flow',
    });
  }

  if (!creds?.client_secret?.trim()) {
    ctx.addIssue({
      path: ['client_credentials', 'client_secret'],
      code: 'custom',
      message: 'Client Secret is required for OAuth2 Client Credentials Flow',
    });
  }
}

export function clientCredentialsToApiPayload(credentials: MCPClientCredentials): MCPAuthenticationMetadata {
  return {
    endpoint: credentials.endpoint,
    client_id: credentials.client_id,
    client_secret: credentials.client_secret,
    scope: credentials.scope || '',
  };
}

type McpServer = ServerResponse<'get', '/api/v2/mcp-servers/{mcp_server_id}'>;

export function apiPayloadToClientCredentials(
  metadata: NonNullable<McpServer['authentication_metadata']>,
): MCPClientCredentials {
  return {
    endpoint: metadata.endpoint,
    client_id: metadata.client_id,
    client_secret: metadata.client_secret,
    scope: metadata.scope,
  };
}

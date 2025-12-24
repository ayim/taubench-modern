// Dialog components
export { NewMcpServerDialog } from './MCPServerDialog/NewMcpServerDialog';
export { EditMcpServerDialog } from './MCPServerDialog/EditMcpServerDialog';

// Auth components for consumers that need custom forms
export { MCPServerAuthFields } from './MCPServerAuth/MCPServerAuthFields';
export { MCPServerClientCredentialsFields } from './MCPServerAuth/MCPServerClientCredentialsFields';

// Shared constants
export { SERVER_TYPE_LABELS, TRANSPORT_OPTIONS_BASE, TRANSPORT_OPTIONS_WITH_STDIO } from './schemas/mcpFormSchema';
export type { McpServerType } from './schemas/mcpFormSchema';

export const DEFAULT_MCP_TYPE = 'generic_mcp' as const;

// MCP Authentication schemas and types
export {
  mcpAuthenticationTypeSchema,
  mcpAuthenticationTypeSelectItems,
  mcpClientCredentialsSchema,
  mcpClientCredentialsPartialSchema,
  mcpAuthenticationMetadataSchema,
  mcpAuthenticationFormSchema,
  refineClientCredentials,
  clientCredentialsToApiPayload,
  apiPayloadToClientCredentials,
  type MCPAuthenticationType,
  type MCPClientCredentials,
  type MCPClientCredentialsPartial,
  type MCPAuthenticationMetadata,
} from './schemas/mcpAuthSchema';

// MCP Form schemas
export {
  mcpTransportSchema,
  mcpServerTypeWithHostedSchema,
  headerEntrySchema,
  headerTypeSelectItems,
  mcpUrlSchema,
  newMcpServerFormSchema,
  editMcpServerFormSchema,
  formHeadersToApiHeaders,
  apiHeadersToFormEntries,
  buildCreateMcpServerPayload,
  buildUpdateMcpServerPayload,
  buildValidationPayload,
  type MCPTransport,
  type MCPServerTypeWithHosted,
  type HeaderEntry,
  type HeaderEntryInput,
  type NewMcpServerFormInput,
  type NewMcpServerFormValues,
  type EditMcpServerFormInput,
  type EditMcpServerFormValues,
  type McpServerFormValues,
} from './schemas/mcpFormSchema';

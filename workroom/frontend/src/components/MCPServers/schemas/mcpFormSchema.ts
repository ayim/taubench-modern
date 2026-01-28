import { z } from 'zod';
import type { ServerRequest, ServerResponse } from '@sema4ai/agent-server-interface';
import {
  mcpAuthenticationTypeSchema,
  mcpClientCredentialsPartialSchema,
  clientCredentialsToApiPayload,
  refineClientCredentials,
} from './mcpAuthSchema';

export type McpServerType = 'generic_mcp' | 'sema4ai_action_server' | 'hosted';

/**
 * Transport types for MCP servers
 */
export const mcpTransportSchema = z.enum(['auto', 'streamable-http', 'sse', 'stdio']);
export type MCPTransport = z.infer<typeof mcpTransportSchema>;

export const SERVER_TYPE_LABELS: Record<McpServerType, string> = {
  generic_mcp: 'Generic MCP',
  sema4ai_action_server: 'Sema4 Action Server',
  hosted: 'Hosted Action Server',
};

export const TRANSPORT_OPTIONS_BASE = [
  { value: 'auto', label: 'Auto (Default)' },
  { value: 'streamable-http', label: 'Streamable HTTP' },
  { value: 'sse', label: 'Server-Sent Events (SSE)' },
] as const;

export const TRANSPORT_OPTIONS_WITH_STDIO = [
  ...TRANSPORT_OPTIONS_BASE,
  { value: 'stdio', label: 'Standard I/O (STDIO)' },
] as const;

export const mcpServerTypeWithHostedSchema = z.enum(['generic_mcp', 'sema4ai_action_server', 'hosted']);
export type MCPServerTypeWithHosted = z.infer<typeof mcpServerTypeWithHostedSchema>;

export const headerEntrySchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string().default(''),
  type: z.enum(['string', 'secret']).default('string'),
});
export type HeaderEntry = z.infer<typeof headerEntrySchema>;
export type HeaderEntryInput = z.input<typeof headerEntrySchema>;

export const headerTypeSelectItems = [
  { value: 'string', label: 'Plain Text' },
  { value: 'secret', label: 'Secret' },
] as const;

export const mcpUrlSchema = z
  .string()
  .optional()
  .transform((val) => (val?.trim() ? val.trim() : undefined));

const baseMcpServerFormSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  type: mcpServerTypeWithHostedSchema.default('generic_mcp'),
  transport: mcpTransportSchema.default('auto'),
  url: mcpUrlSchema,
  headersKV: z.array(headerEntrySchema).default([]),
  agentPackageSecrets: z.record(z.string(), z.string()).optional(),
  authentication_type: mcpAuthenticationTypeSchema.default('none'),
  client_credentials: mcpClientCredentialsPartialSchema.optional(),
});

export const newMcpServerFormSchema = baseMcpServerFormSchema
  .extend({
    agentPackageFile: z.instanceof(File).optional(),
  })
  .superRefine((values, ctx) => {
    if (values.type === 'hosted') {
      if (!values.agentPackageFile && !values.url) {
        ctx.addIssue({
          code: 'custom',
          path: ['url'],
          message: 'Action Server URL is required when no agent package is uploaded',
        });
      }
    } else if (values.transport !== 'stdio' && !values.url) {
      ctx.addIssue({
        code: 'custom',
        path: ['url'],
        message: 'URL is required for this transport',
      });
    }

    refineClientCredentials(values, ctx);
  });

export type NewMcpServerFormInput = z.input<typeof newMcpServerFormSchema>;
export type NewMcpServerFormValues = z.output<typeof newMcpServerFormSchema>;

export const editMcpServerFormSchema = baseMcpServerFormSchema
  .extend({
    command: z.string().optional(),
    argsText: z.string().optional(),
    cwd: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    refineClientCredentials(values, ctx);
  });

export type EditMcpServerFormInput = z.input<typeof editMcpServerFormSchema>;
export type EditMcpServerFormValues = z.output<typeof editMcpServerFormSchema>;

export type McpServerFormValues = NewMcpServerFormValues | EditMcpServerFormValues;

type ApiHeaders = ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>['headers'];

export const formHeadersToApiHeaders = (entries: HeaderEntryInput[]): ApiHeaders | undefined => {
  const headers = entries.reduce<NonNullable<ApiHeaders>>((acc, entry) => {
    const headerKey = entry.key?.trim();
    const headerValue = entry.value ?? '';

    if (!headerKey) {
      return acc;
    }

    if (entry.type === 'secret') {
      acc[headerKey] = { type: 'secret', value: headerValue };
    } else {
      acc[headerKey] = headerValue;
    }
    return acc;
  }, {});

  return Object.keys(headers).length > 0 ? headers : undefined;
};

export const apiHeadersToFormEntries = (
  headers: ApiHeaders | undefined | null,
): {
  entries: HeaderEntry[];
  secrets: Record<string, string>;
} => {
  if (!headers) {
    return { entries: [], secrets: {} };
  }

  const result = Object.entries(headers).reduce<{ entries: HeaderEntry[]; secrets: Record<string, string> }>(
    (acc, [key, value]) => {
      if (value && typeof value === 'object' && 'type' in value && value.type === 'secret') {
        acc.entries.push({ key, value: value.value ?? '', type: 'secret' });
        acc.secrets[key] = value.value ?? '';
      } else {
        acc.entries.push({ key, value: (value as string) ?? '', type: 'string' });
      }
      return acc;
    },
    { entries: [], secrets: {} },
  );

  return result;
};

type OAuthConfig = ServerRequest<'post', '/api/v2/mcp-servers/', 'requestBody'>['oauth_config'];
type OAuthConfigUpdate = {
  authentication_type: NonNullable<
    NonNullable<
      ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>['oauth_config']
    >['authentication_type']
  >;
  authentication_metadata?: NonNullable<
    ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>['oauth_config']
  >['authentication_metadata'];
} | null;

const buildOAuthConfig = (input: McpServerFormValues): OAuthConfig => {
  if (input.authentication_type === 'none') {
    return null;
  }

  if (input.authentication_type === 'oauth2-client-credentials') {
    const creds = input.client_credentials;
    // These are guaranteed by superRefine validation when auth type is oauth2-client-credentials
    const endpoint = creds?.endpoint?.trim();
    const clientId = creds?.client_id?.trim();
    const clientSecret = creds?.client_secret?.trim();

    if (!endpoint || !clientId || !clientSecret) {
      // This shouldn't happen due to form validation, but handle gracefully
      return null;
    }

    return {
      authentication_type: 'oauth2-client-credentials',
      authentication_metadata: clientCredentialsToApiPayload({
        endpoint,
        client_id: clientId,
        client_secret: clientSecret,
        scope: creds?.scope,
      }),
    };
  }

  // For other auth types (e.g., oauth2-authorization-code), return basic config
  return {
    authentication_type: input.authentication_type,
  };
};

const buildOAuthConfigForUpdate = (input: McpServerFormValues): OAuthConfigUpdate => {
  switch (input.authentication_type) {
    case 'none':
      return null;

    case 'oauth2-client-credentials': {
      const creds = input.client_credentials;
      const endpoint = creds?.endpoint?.trim();
      const clientId = creds?.client_id?.trim();
      const clientSecret = creds?.client_secret?.trim();

      if (!endpoint || !clientId || !clientSecret) {
        return null;
      }

      return {
        authentication_type: 'oauth2-client-credentials',
        authentication_metadata: {
          endpoint,
          client_id: clientId,
          client_secret: clientSecret,
          scope: creds?.scope ?? null,
        },
      };
    }

    case 'oauth2-authorization-code':
      return { authentication_type: input.authentication_type };

    default:
      input.authentication_type satisfies never;
      return { authentication_type: input.authentication_type };
  }
};

const getAgentPackageSecretEntries = (agentPackageSecrets: Record<string, string> | undefined): HeaderEntry[] => {
  return (
    Object.entries(agentPackageSecrets ?? {})
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      .filter(([_, value]) => value && value.trim() !== '')
      .map(([key, value]) => ({ key, value, type: 'secret' as const }))
  );
};

type CreateMcpServerBody = ServerRequest<'post', '/api/v2/mcp-servers/', 'requestBody'>;

export const buildCreateMcpServerPayload = (input: NewMcpServerFormValues): CreateMcpServerBody => {
  let headerEntries = input.headersKV;

  if (input.type === 'hosted' && input.agentPackageSecrets) {
    const secretEntries = getAgentPackageSecretEntries(input.agentPackageSecrets);
    headerEntries = [...headerEntries, ...secretEntries];
  }

  const headers = formHeadersToApiHeaders(headerEntries);
  const transport = input.type === 'hosted' ? 'streamable-http' : input.transport;
  const url = input.type === 'hosted' && input.agentPackageFile ? 'TODO' : input.url;
  const apiType = input.type === 'hosted' ? 'sema4ai_action_server' : input.type;

  return {
    name: input.name,
    type: apiType,
    transport,
    url,
    force_serial_tool_calls: false,
    headers,
    oauth_config: buildOAuthConfig(input),
  };
};

type McpServerApiType = 'generic_mcp' | 'sema4ai_action_server';

type McpServerCorePayload = {
  name: string;
  type: McpServerApiType;
  transport: MCPTransport;
  url: string | undefined;
  headers: ReturnType<typeof formHeadersToApiHeaders>;
  force_serial_tool_calls: boolean;
  command: string | undefined;
  args: string[] | undefined;
  cwd: string | undefined;
  env: McpServer['env'];
};

type UpdateMcpServerPayload = ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>;
type CreateMcpServerPayload = ServerRequest<'post', '/api/v2/mcp-servers/', 'requestBody'>;

const buildMcpServerCorePayload = (
  input: EditMcpServerFormValues,
  original: { force_serial_tool_calls: McpServer['force_serial_tool_calls']; env: McpServer['env'] },
  options: { isHostedWithMetadata: boolean },
): McpServerCorePayload => {
  const allEntries =
    options.isHostedWithMetadata && input.agentPackageSecrets
      ? [...input.headersKV, ...getAgentPackageSecretEntries(input.agentPackageSecrets)]
      : input.headersKV;

  const isStdio = input.transport === 'stdio';
  const apiType: McpServerApiType = input.type === 'hosted' ? 'sema4ai_action_server' : input.type;

  return {
    name: input.name,
    type: apiType,
    transport: input.transport,
    url: isStdio ? undefined : input.url,
    headers: formHeadersToApiHeaders(allEntries),
    force_serial_tool_calls: original.force_serial_tool_calls,
    command: isStdio ? input.command : undefined,
    args: isStdio ? input.argsText?.split(/\s+/).filter(Boolean) : undefined,
    cwd: isStdio ? input.cwd : undefined,
    env: isStdio ? original.env : {},
  };
};

type McpServer = ServerResponse<'get', '/api/v2/mcp-servers/{mcp_server_id}'>;

export const buildUpdateMcpServerPayload = (
  input: EditMcpServerFormValues,
  original: { force_serial_tool_calls: McpServer['force_serial_tool_calls']; env: McpServer['env'] },
  options: { isHostedWithMetadata: boolean },
): UpdateMcpServerPayload => {
  const core = buildMcpServerCorePayload(input, original, options);

  return {
    name: core.name,
    type: core.type,
    transport: core.transport,
    url: core.url ?? null,
    headers: core.headers ?? null,
    force_serial_tool_calls: core.force_serial_tool_calls,
    command: core.command ?? null,
    args: core.args ?? null,
    cwd: core.cwd ?? null,
    env: core.env ?? null,
    oauth_config: buildOAuthConfigForUpdate(input),
  };
};

export const buildValidationPayload = (
  input: EditMcpServerFormValues,
  original: { force_serial_tool_calls: McpServer['force_serial_tool_calls']; env: McpServer['env'] },
  options: { isHostedWithMetadata: boolean },
): CreateMcpServerPayload => {
  const core = buildMcpServerCorePayload(input, original, options);

  return {
    name: core.name,
    type: core.type,
    transport: core.transport,
    url: core.url,
    headers: core.headers,
    force_serial_tool_calls: core.force_serial_tool_calls,
    command: core.command,
    args: core.args,
    cwd: core.cwd,
    env: core.env,
    oauth_config: buildOAuthConfigForUpdate(input),
  };
};

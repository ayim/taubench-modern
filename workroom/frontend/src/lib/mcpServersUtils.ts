import z from 'zod';
import { paths, components } from '@sema4ai/agent-server-interface';

type MCPServerCreate = paths['/api/v2/mcp-servers/']['post']['requestBody']['content']['application/json'];
type MCPServerUpdate =
  paths['/api/v2/mcp-servers/{mcp_server_id}']['put']['requestBody']['content']['application/json'];

export const mcpTransportSchema = z.enum(['auto', 'streamable-http', 'sse', 'stdio']);
export const mcpServerTypeSchema = z.enum(['generic_mcp', 'sema4ai_action_server', 'hosted']);
export const mcpUrlSchema = z
  .string()
  .optional()
  .transform((val) => (val?.trim() ? val.trim() : undefined));

export const mcpTransportSelectItems = [
  { value: 'auto', label: 'Auto (Default)' },
  { value: 'streamable-http', label: 'Streamable HTTP' },
  { value: 'sse', label: 'SSE' },
  { value: 'stdio', label: 'STDIO' },
] as const;

export const mcpTypeSelectItems = [
  { value: 'generic_mcp', label: 'Generic MCP' },
  { value: 'sema4ai_action_server', label: 'Sema4 Action Server' },
] as const;

export const mcpTypeSelectItemsWithHosted = [
  ...mcpTypeSelectItems,
  { value: 'hosted', label: 'Hosted Action Server' },
] as const;

export const headerTypeSelectItems = [
  { value: 'string', label: 'Plain Text' },
  { value: 'secret', label: 'Secret' },
] as const;

type McpTransport = z.infer<typeof mcpTransportSchema>;

export const parseTransport = (value: string): McpTransport => {
  const result = mcpTransportSchema.safeParse(value);
  return result.success ? result.data : 'auto';
};

export const headerEntrySchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string().default(''),
  type: z.enum(['string', 'secret']).default('string'),
});
type HeaderEntry = z.infer<typeof headerEntrySchema>;
type HeaderEntryInput = z.input<typeof headerEntrySchema>;

const baseMcpServerFormSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  type: mcpServerTypeSchema.default('generic_mcp'),
  transport: mcpTransportSchema.default('auto'),
  url: mcpUrlSchema,
  headersKV: z.array(headerEntrySchema).default([]),
  agentPackageSecrets: z.record(z.string(), z.string()).optional(),
});

export const newMcpServerFormSchema = baseMcpServerFormSchema
  .extend({
    agentPackageFile: z.instanceof(File).optional(),
  })
  .superRefine((values, ctx) => {
    if (values.type === 'hosted') {
      if (!values.agentPackageFile && !values.url) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['url'],
          message: 'Action Server URL is required when no agent package is uploaded',
        });
      }
    } else if (values.transport !== 'stdio' && !values.url) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['url'], message: 'URL is required for this transport' });
    }
  });
export type NewMcpServerFormInput = z.input<typeof newMcpServerFormSchema>;
export type NewMcpServerFormValues = z.output<typeof newMcpServerFormSchema>;

export const editMcpServerFormSchema = baseMcpServerFormSchema.extend({
  command: z.string().optional(),
  argsText: z.string().optional(),
  cwd: z.string().optional(),
});
export type EditMcpServerFormInput = z.input<typeof editMcpServerFormSchema>;
export type EditMcpServerFormValues = z.output<typeof editMcpServerFormSchema>;

type ApiHeaders = MCPServerCreate['headers'];
type McpServerHeaders = components['schemas']['MCPServer']['headers'];

export function formHeadersToApiHeaders(entries: HeaderEntryInput[]): ApiHeaders | undefined {
  const headers: NonNullable<ApiHeaders> = {};

  for (const entry of entries) {
    const headerKey = entry.key?.trim();
    const headerValue = entry.value ?? '';

    if (!headerKey) {
      continue;
    }

    if (entry.type === 'secret') {
      headers[headerKey] = { type: 'secret', value: headerValue };
    } else {
      headers[headerKey] = headerValue;
    }
  }

  return Object.keys(headers).length > 0 ? headers : undefined;
}

export function apiHeadersToFormEntries(headers: McpServerHeaders | undefined | null): {
  entries: HeaderEntry[];
  secrets: Record<string, string>;
} {
  const entries: HeaderEntry[] = [];
  const secrets: Record<string, string> = {};

  if (!headers) {
    return { entries, secrets };
  }

  for (const [key, value] of Object.entries(headers)) {
    if (value && typeof value === 'object' && 'type' in value && value.type === 'secret') {
      entries.push({ key, value: value.value ?? '', type: 'secret' });
      secrets[key] = value.value ?? '';
    } else {
      entries.push({ key, value: (value as string) ?? '', type: 'string' });
    }
  }

  return { entries, secrets };
}

function getAgentPackageSecretEntries(agentPackageSecrets: Record<string, string> | undefined): HeaderEntry[] {
  return Object.entries(agentPackageSecrets ?? {})
    .filter(([_, value]) => value && value.trim() !== '')
    .map(([key, value]) => ({ key, value, type: 'secret' as const }));
}

export function buildCreateMcpServerPayload(input: NewMcpServerFormValues): MCPServerCreate {
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
  };
}

export function buildUpdateMcpServerPayload(
  input: EditMcpServerFormValues,
  original: { force_serial_tool_calls: boolean; env?: Record<string, unknown> | null },
  options: { isHostedWithMetadata: boolean },
): MCPServerUpdate {
  const allEntries =
    options.isHostedWithMetadata && input.agentPackageSecrets
      ? [...input.headersKV, ...getAgentPackageSecretEntries(input.agentPackageSecrets)]
      : input.headersKV;

  const isStdio = input.transport === 'stdio';
  const apiType = input.type === 'hosted' ? 'sema4ai_action_server' : input.type;

  return {
    name: input.name,
    type: apiType,
    transport: input.transport,
    url: isStdio ? null : input.url || null,
    headers: formHeadersToApiHeaders(allEntries) ?? null,
    force_serial_tool_calls: original.force_serial_tool_calls,
    ...(isStdio && {
      command: input.command || null,
      args: input.argsText?.split(/\s+/).filter(Boolean) || null,
      cwd: input.cwd || null,
      env: (original.env as Record<string, string>) ?? null,
    }),
  };
}

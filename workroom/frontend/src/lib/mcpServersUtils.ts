import z from 'zod';
import { paths } from '@sema4ai/agent-server-interface';

type MCPServerCreate = paths['/api/v2/mcp-servers/']['post']['requestBody']['content']['application/json'];

export const newMcpServerFormSchema = z
  .object({
    name: z.string().min(1, 'Name is required'),
    type: z.enum(['generic_mcp', 'sema4ai_action_server', 'hosted']).default('generic_mcp'),
    transport: z.enum(['auto', 'streamable-http', 'sse', 'stdio']),
    url: z
      .string()
      .optional()
      .transform((val) => (val?.trim() ? val.trim() : undefined)),
    headersKV: z
      .array(
        z.object({
          key: z.string().min(1, 'Key is required'),
          value: z.string().optional().default(''),
          type: z.enum(['string', 'secret']).optional().default('string'),
        }),
      )
      .default([]),
    agentPackageFile: z.instanceof(File).optional(),
    agentPackageSecrets: z.record(z.string(), z.string()).optional(),
  })
  .superRefine((values, ctx) => {
    if (values.type === 'hosted') {
      // Hosted type requires agent package file
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

const formHeadersToApiHeaders = (entries: NewMcpServerFormValues['headersKV']) => {
  const headers: MCPServerCreate['headers'] = {};

  for (const entry of entries) {
    const headerKey = entry.key?.trim();
    const headerValue = entry.value ?? '';
    const isSecret = entry.type === 'secret';

    if (!headerKey) {
      continue;
    }

    if (isSecret) {
      headers[headerKey] = { type: 'secret', value: headerValue };
    } else {
      headers[headerKey] = headerValue;
    }
  }

  return Object.keys(headers).length > 0 ? headers : undefined;
};

const getAgentPackageSecrets = (input: { agentPackageSecrets: NewMcpServerFormValues['agentPackageSecrets'] }) => {
  const secretEntries = Object.entries(input.agentPackageSecrets ?? {})
    .filter(([_, value]) => value && value.trim() !== '')
    .map(([key, value]) => {
      return {
        key,
        value,
        type: 'secret' as const,
      };
    });
  return secretEntries;
};

export function getCreateMcpServerBody(input: NewMcpServerFormValues): MCPServerCreate {
  let headerEntries = input.headersKV;

  if (input.type === 'hosted' && input.agentPackageSecrets) {
    const secretEntries = getAgentPackageSecrets({ agentPackageSecrets: input.agentPackageSecrets });
    headerEntries = [...headerEntries, ...secretEntries];
  }

  const headers = formHeadersToApiHeaders(headerEntries);

  // Hosted type always uses streamable-http, others use their configured transport
  const transport = input.type === 'hosted' ? 'streamable-http' : input.transport;

  // For hosted type with uploaded files, use placeholder URL (backend requirement)
  const url = input.type === 'hosted' && input.agentPackageFile ? 'TODO' : input.url;

  // Map 'hosted' to 'sema4ai_action_server' for the API
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

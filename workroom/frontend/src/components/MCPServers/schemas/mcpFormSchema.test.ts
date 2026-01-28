import { describe, expect, it } from 'vitest';
import {
  formHeadersToApiHeaders,
  apiHeadersToFormEntries,
  buildCreateMcpServerPayload,
  buildUpdateMcpServerPayload,
  buildValidationPayload,
  newMcpServerFormSchema,
  editMcpServerFormSchema,
  type HeaderEntryInput,
  type NewMcpServerFormValues,
  type EditMcpServerFormValues,
} from './mcpFormSchema';

describe('formHeadersToApiHeaders', () => {
  it('returns undefined for empty array', () => {
    expect(formHeadersToApiHeaders([])).toBeUndefined();
  });

  it.each([
    {
      entries: [{ key: 'Authorization', value: 'Bearer token', type: 'string' as const }],
      expected: { Authorization: 'Bearer token' },
      description: 'string header entry',
    },
    {
      entries: [{ key: 'API-Key', value: 'secret-value', type: 'secret' as const }],
      expected: { 'API-Key': { type: 'secret', value: 'secret-value' } },
      description: 'secret header entry',
    },
    {
      entries: [
        { key: 'Content-Type', value: 'application/json', type: 'string' as const },
        { key: 'API-Key', value: 'secret-value', type: 'secret' as const },
      ],
      expected: { 'Content-Type': 'application/json', 'API-Key': { type: 'secret', value: 'secret-value' } },
      description: 'mixed header entries',
    },
    {
      entries: [{ key: '  Authorization  ', value: 'token', type: 'string' as const }],
      expected: { Authorization: 'token' },
      description: 'keys with whitespace (trims)',
    },
    {
      entries: [{ key: 'Header', value: 'value' }],
      expected: { Header: 'value' },
      description: 'default type (string) when not specified',
    },
  ])('converts $description', ({ entries, expected }) => {
    expect(formHeadersToApiHeaders(entries)).toEqual(expected);
  });

  it.each([
    {
      entries: [
        { key: '', value: 'value1', type: 'string' as const },
        { key: 'Valid', value: 'value2', type: 'string' as const },
      ],
      description: 'empty keys',
    },
    {
      entries: [
        { key: '   ', value: 'value1', type: 'string' as const },
        { key: 'Valid', value: 'value2', type: 'string' as const },
      ],
      description: 'whitespace-only keys',
    },
  ])('skips entries with $description', ({ entries }) => {
    expect(formHeadersToApiHeaders(entries)).toEqual({ Valid: 'value2' });
  });

  it('handles undefined value as empty string', () => {
    const entries: HeaderEntryInput[] = [{ key: 'Header', value: undefined as unknown as string, type: 'string' }];
    expect(formHeadersToApiHeaders(entries)).toEqual({ Header: '' });
  });
});

describe('apiHeadersToFormEntries', () => {
  it.each([
    { headers: null, description: 'null headers' },
    { headers: undefined, description: 'undefined headers' },
  ])('returns empty entries and secrets for $description', ({ headers }) => {
    expect(apiHeadersToFormEntries(headers)).toEqual({ entries: [], secrets: {} });
  });

  it('converts string header to form entry', () => {
    const result = apiHeadersToFormEntries({ Authorization: 'Bearer token' });
    expect(result.entries).toEqual([{ key: 'Authorization', value: 'Bearer token', type: 'string' }]);
    expect(result.secrets).toEqual({});
  });

  it('converts secret header to form entry and tracks in secrets', () => {
    const result = apiHeadersToFormEntries({ 'API-Key': { type: 'secret' as const, value: 'secret-value' } });
    expect(result.entries).toEqual([{ key: 'API-Key', value: 'secret-value', type: 'secret' }]);
    expect(result.secrets).toEqual({ 'API-Key': 'secret-value' });
  });

  it('converts mixed headers correctly', () => {
    const result = apiHeadersToFormEntries({
      'Content-Type': 'application/json',
      'API-Key': { type: 'secret' as const, value: 'secret-value' },
    });
    expect(result.entries).toHaveLength(2);
    expect(result.entries).toContainEqual({ key: 'Content-Type', value: 'application/json', type: 'string' });
    expect(result.entries).toContainEqual({ key: 'API-Key', value: 'secret-value', type: 'secret' });
    expect(result.secrets).toEqual({ 'API-Key': 'secret-value' });
  });

  it('handles secret with undefined value', () => {
    const result = apiHeadersToFormEntries({
      'API-Key': { type: 'secret' as const, value: undefined as unknown as string },
    });
    expect(result.entries).toEqual([{ key: 'API-Key', value: '', type: 'secret' }]);
    expect(result.secrets).toEqual({ 'API-Key': '' });
  });
});

describe('buildCreateMcpServerPayload', () => {
  const baseInput: NewMcpServerFormValues = {
    name: 'Test Server',
    type: 'generic_mcp',
    transport: 'auto',
    url: 'https://example.com/mcp',
    headersKV: [],
    authentication_type: 'none',
    client_credentials: undefined,
  };

  it('builds payload for generic MCP server', () => {
    const result = buildCreateMcpServerPayload(baseInput);
    expect(result).toEqual({
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
      force_serial_tool_calls: false,
      headers: undefined,
      oauth_config: null,
    });
  });

  it('builds payload for sema4ai action server', () => {
    const input: NewMcpServerFormValues = { ...baseInput, type: 'sema4ai_action_server' };
    const result = buildCreateMcpServerPayload(input);
    expect(result.type).toBe('sema4ai_action_server');
  });

  it('builds payload for hosted server with URL', () => {
    const input: NewMcpServerFormValues = { ...baseInput, type: 'hosted' };
    const result = buildCreateMcpServerPayload(input);
    expect(result.type).toBe('sema4ai_action_server');
    expect(result.transport).toBe('streamable-http');
    expect(result.url).toBe('https://example.com/mcp');
  });

  it('includes headers when provided', () => {
    const input: NewMcpServerFormValues = {
      ...baseInput,
      headersKV: [{ key: 'Authorization', value: 'Bearer token', type: 'string' }],
    };
    const result = buildCreateMcpServerPayload(input);
    expect(result.headers).toEqual({ Authorization: 'Bearer token' });
  });

  it('includes agent package secrets as secret headers for hosted type', () => {
    const input: NewMcpServerFormValues = {
      ...baseInput,
      type: 'hosted',
      agentPackageSecrets: { API_KEY: 'my-api-key', EMPTY_SECRET: '' },
    };
    const result = buildCreateMcpServerPayload(input);
    expect(result.headers).toEqual({ API_KEY: { type: 'secret', value: 'my-api-key' } });
  });

  it('builds oauth config for client credentials flow', () => {
    const input: NewMcpServerFormValues = {
      ...baseInput,
      authentication_type: 'oauth2-client-credentials',
      client_credentials: {
        endpoint: 'https://auth.example.com/token',
        client_id: 'my-client-id',
        client_secret: 'my-client-secret',
        scope: 'read write',
      },
    };
    const result = buildCreateMcpServerPayload(input);
    expect(result.oauth_config).toEqual({
      authentication_type: 'oauth2-client-credentials',
      authentication_metadata: {
        endpoint: 'https://auth.example.com/token',
        client_id: 'my-client-id',
        client_secret: 'my-client-secret',
        scope: 'read write',
      },
    });
  });

  it('returns null oauth config when auth type is none', () => {
    const result = buildCreateMcpServerPayload(baseInput);
    expect(result.oauth_config).toBeNull();
  });
});

describe('buildUpdateMcpServerPayload', () => {
  const baseInput: EditMcpServerFormValues = {
    name: 'Test Server',
    type: 'generic_mcp',
    transport: 'auto',
    url: 'https://example.com/mcp',
    headersKV: [],
    authentication_type: 'none',
    client_credentials: undefined,
  };

  const baseOriginal = { force_serial_tool_calls: false, env: {} };

  it('builds payload for URL-based server', () => {
    const result = buildUpdateMcpServerPayload(baseInput, baseOriginal, { isHostedWithMetadata: false });
    expect(result).toEqual({
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
      headers: null,
      force_serial_tool_calls: false,
      command: null,
      oauth_config: null,
      args: null,
      cwd: null,
      env: {},
    });
  });

  it('builds payload for stdio transport', () => {
    const input: EditMcpServerFormValues = {
      ...baseInput,
      transport: 'stdio',
      command: '/usr/local/bin/mcp-server',
      argsText: '--flag value',
      cwd: '/home/user',
    };
    const original = { force_serial_tool_calls: true, env: { PATH: '/usr/bin' } };
    const result = buildUpdateMcpServerPayload(input, original, { isHostedWithMetadata: false });

    expect(result.url).toBeNull();
    expect(result.command).toBe('/usr/local/bin/mcp-server');
    expect(result.args).toEqual(['--flag', 'value']);
    expect(result.cwd).toBe('/home/user');
    expect(result.env).toEqual({ PATH: '/usr/bin' });
    expect(result.force_serial_tool_calls).toBe(true);
  });

  it('converts hosted type to sema4ai_action_server', () => {
    const input: EditMcpServerFormValues = { ...baseInput, type: 'hosted' };
    const result = buildUpdateMcpServerPayload(input, baseOriginal, { isHostedWithMetadata: false });
    expect(result.type).toBe('sema4ai_action_server');
  });

  it('includes agent package secrets when isHostedWithMetadata is true', () => {
    const input: EditMcpServerFormValues = {
      ...baseInput,
      type: 'hosted',
      agentPackageSecrets: { API_KEY: 'my-api-key' },
    };
    const result = buildUpdateMcpServerPayload(input, baseOriginal, { isHostedWithMetadata: true });
    expect(result.headers).toEqual({ API_KEY: { type: 'secret', value: 'my-api-key' } });
  });

  it('does not include agent package secrets when isHostedWithMetadata is false', () => {
    const input: EditMcpServerFormValues = {
      ...baseInput,
      agentPackageSecrets: { API_KEY: 'my-api-key' },
    };
    const result = buildUpdateMcpServerPayload(input, baseOriginal, { isHostedWithMetadata: false });
    expect(result.headers).toBeNull();
  });

  it('splits argsText by whitespace', () => {
    const input: EditMcpServerFormValues = {
      ...baseInput,
      transport: 'stdio',
      command: 'cmd',
      argsText: '  --flag   value  --other  ',
    };
    const result = buildUpdateMcpServerPayload(input, baseOriginal, { isHostedWithMetadata: false });
    expect(result.args).toEqual(['--flag', 'value', '--other']);
  });
});

describe('buildValidationPayload', () => {
  const baseInput: EditMcpServerFormValues = {
    name: 'Test Server',
    type: 'generic_mcp',
    transport: 'auto',
    url: 'https://example.com/mcp',
    headersKV: [],
    authentication_type: 'none',
    client_credentials: undefined,
  };

  const baseOriginal = { force_serial_tool_calls: false, env: {} };

  it('builds validation payload with undefined values instead of null', () => {
    const result = buildValidationPayload(baseInput, baseOriginal, { isHostedWithMetadata: false });
    expect(result).toEqual({
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
      headers: undefined,
      oauth_config: null,
      force_serial_tool_calls: false,
      command: undefined,
      args: undefined,
      cwd: undefined,
      env: {},
    });
  });

  it('builds validation payload for stdio transport', () => {
    const input: EditMcpServerFormValues = {
      ...baseInput,
      transport: 'stdio',
      command: '/usr/local/bin/mcp-server',
      argsText: '--flag value',
      cwd: '/home/user',
    };
    const original = { force_serial_tool_calls: false, env: { PATH: '/usr/bin' } };
    const result = buildValidationPayload(input, original, { isHostedWithMetadata: false });

    expect(result.url).toBeUndefined();
    expect(result.command).toBe('/usr/local/bin/mcp-server');
    expect(result.args).toEqual(['--flag', 'value']);
    expect(result.cwd).toBe('/home/user');
    expect(result.env).toEqual({ PATH: '/usr/bin' });
  });
});

describe('newMcpServerFormSchema', () => {
  it('validates basic generic MCP server', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('requires name', () => {
    const input = {
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('requires URL for non-stdio transport', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((i) => i.message === 'URL is required for this transport')).toBe(true);
    }
  });

  it('allows stdio transport without URL', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'stdio',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('requires URL for hosted type without agent package file', () => {
    const input = {
      name: 'Test Server',
      type: 'hosted',
      transport: 'auto',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some(
          (i) => i.message === 'Action Server URL is required when no agent package is uploaded',
        ),
      ).toBe(true);
    }
  });

  it('allows hosted type with URL', () => {
    const input = {
      name: 'Test Server',
      type: 'hosted',
      transport: 'auto',
      url: 'https://example.com/mcp',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('validates OAuth2 client credentials fields when auth type selected', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
      authentication_type: 'oauth2-client-credentials',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((i) => i.message);
      expect(messages).toContain('Endpoint is required for OAuth2 Client Credentials Flow');
      expect(messages).toContain('Client ID is required for OAuth2 Client Credentials Flow');
      expect(messages).toContain('Client Secret is required for OAuth2 Client Credentials Flow');
    }
  });

  it('validates endpoint is a valid URL', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
      authentication_type: 'oauth2-client-credentials',
      client_credentials: {
        endpoint: 'not-a-url',
        client_id: 'client-id',
        client_secret: 'client-secret',
      },
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((i) => i.message === 'Endpoint must be a valid URL')).toBe(true);
    }
  });

  it('accepts valid OAuth2 client credentials', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
      authentication_type: 'oauth2-client-credentials',
      client_credentials: {
        endpoint: 'https://auth.example.com/token',
        client_id: 'client-id',
        client_secret: 'client-secret',
      },
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('trims URL whitespace', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: '  https://example.com/mcp  ',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.url).toBe('https://example.com/mcp');
    }
  });

  it('converts whitespace-only URL to undefined', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'stdio',
      url: '   ',
    };
    const result = newMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.url).toBeUndefined();
    }
  });
});

describe('editMcpServerFormSchema', () => {
  it('validates basic edit form', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
    };
    const result = editMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('allows stdio fields', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'stdio',
      command: '/usr/local/bin/mcp-server',
      argsText: '--flag value',
      cwd: '/home/user',
    };
    const result = editMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.command).toBe('/usr/local/bin/mcp-server');
      expect(result.data.argsText).toBe('--flag value');
      expect(result.data.cwd).toBe('/home/user');
    }
  });

  it('validates OAuth2 client credentials when selected', () => {
    const input = {
      name: 'Test Server',
      type: 'generic_mcp',
      transport: 'auto',
      url: 'https://example.com/mcp',
      authentication_type: 'oauth2-client-credentials',
    };
    const result = editMcpServerFormSchema.safeParse(input);
    expect(result.success).toBe(false);
  });
});

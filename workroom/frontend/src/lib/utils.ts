import { UserTenant } from '~/queries/tenants';
import { getBasePath } from '~/utils/base';
import type { CreateMcpServerBody, McpServerResponse, UpdateMcpServerBody } from '~/queries/mcpServers';

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: 'numeric',
  hour12: true,
});

export const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  const month = date.toLocaleDateString('en-US', { month: 'short' });
  const day = date.getDate();
  const year = date.getFullYear();
  const hour = date.getHours();
  const minute = date.getMinutes();
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour % 12 || 12;
  const displayMinute = minute.toString().padStart(2, '0');

  return `${month} ${day}, ${year} at ${displayHour}:${displayMinute} ${ampm}`;
};

export const formatDatetime = (date?: Date | string | null): string | undefined => {
  if (!date) return undefined;
  const result = dateTimeFormatter.format(new Date(date));
  return result;
};

export const getTenantEnvironmentUrl = (tenant: UserTenant): string => {
  if (/^https?:\/\//i.test(tenant.environment.url)) {
    return tenant.environment.url.endsWith('/') ? tenant.environment.url : `${tenant.environment.url}/`;
  }

  const relativeLocal = new URL(
    tenant.environment.url,
    `${window.location.protocol}//${window.location.host}`,
  ).toString();
  return relativeLocal.endsWith('/') ? relativeLocal : `${relativeLocal}/`;
};

const isLocalhostOrigin = (origin: string) => /^https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$/i.test(origin);

export const getTenantWorkoomRedirect = ({
  tenant,
  location,
}: {
  tenant: UserTenant;
  location: Location;
}): { href: string } | null => {
  // WHY?
  // Each ACE has one Work Room / Agent version combination
  // When using the MAIN Work Room, it is possible to hit a mismatching agent server version: each tenant can be on any given ACE
  // Instead of having to go through full backward and forward compatibility
  // We point to the matching Work Room ACE URL

  const isDev = isLocalhostOrigin(location.origin);

  if (isDev) {
    return null;
  }

  // Pick the correct redirect URL. On newer ACEs (>=1.5.0) the tenant_workroom_url value will be set to a URL
  // like so: https://<host>/tenants/<tenantId> - whereas on older ACEs, workroom_url will be set to:
  // https://<host>
  const tenantRedirectUrl = tenant.environment.tenant_workroom_url ?? tenant.environment.workroom_url ?? null;

  if (tenantRedirectUrl === null) {
    return null;
  }

  return {
    href: tenantRedirectUrl,
  };
};

export const beautifyLabel = (value: string): string => {
  const id = value.split(':')[1] || value;
  return id
    .replace(/-/g, ' ')
    .replace(/^gpt /, 'GPT ')
    .replace(/^o(\d)/i, (_, d) => `O${d} `)
    .replace(/\bmini\b/i, 'Mini')
    .replace(/\bhigh\b/i, 'High')
    .replace(/\bopenai service\b/i, 'OpenAI Service')
    .replace(/\bamazon bedrock\b/i, 'Amazon Bedrock')
    .replace(/\bazure\b/i, 'Azure')
    .replace(/\bopenai\b/i, 'OpenAI')
    .replace(/\bbedrock\b/i, 'Bedrock')
    .replace(/\b(\w)/g, (m) => m.toUpperCase());
};

export const joinURL = (...parts: Array<string>): string => {
  return parts
    .join('/')
    .replace(/[/]+/g, '/')
    .replace(/^(.+):\//, '$1://')
    .replace(/^file:/, 'file:/')
    .replace(/\/(\?|&|#[^!])/g, '$1')
    .replace(/\?/g, '&')
    .replace('&', '?');
};

export const resolveWorkroomURL = (
  path: string,
  baseUrl: string = `${window.location.protocol}//${window.location.host}`,
): string => joinURL(baseUrl, getBasePath(), path);

export type HeaderEntry = { key: string; value?: string; type?: 'string' | 'secret' };

export function entriesToHeaders(entries: HeaderEntry[] | undefined | null): Record<string, string> {
  const normalized = (entries || [])
    .filter((entry) => entry && typeof entry.key === 'string' && entry.key.trim().length > 0)
    .map((entry) => [entry.key, entry.value ?? '']);
  return Object.fromEntries(normalized);
}

export function headersToEntries(headers?: Record<string, string | undefined> | null): HeaderEntry[] {
  if (!headers) return [];
  return Object.entries(headers).map(([key, value]) => ({ key, value: value ?? '', type: 'string' }));
}

export function buildCreateMcpBody(values: {
  name: string;
  transport: CreateMcpServerBody['transport'];
  url?: string;
  headerEntries?: HeaderEntry[];
}): CreateMcpServerBody {
  const headers = entriesToHeaders(values.headerEntries);
  return {
    name: values.name,
    transport: values.transport,
    url: values.url || undefined,
    headers: Object.keys(headers).length ? headers : undefined,
  } as CreateMcpServerBody;
}

export function buildUpdateMcpBody(
  values: {
    name: string;
    transport: UpdateMcpServerBody['transport'];
    url?: string;
    headerEntries?: HeaderEntry[];
    command?: string;
    argsText?: string;
    cwd?: string;
  },
  initial: McpServerResponse,
): UpdateMcpServerBody {
  const headers = entriesToHeaders(values.headerEntries);
  const base: UpdateMcpServerBody = {
    name: values.name,
    transport: values.transport,
    url: values.transport === 'stdio' ? null : values.url || null,
    headers: Object.keys(headers).length ? headers : null,
  } as UpdateMcpServerBody;

  if (values.transport === 'stdio') {
    const parsedArgs = (values.argsText || '')
      .split(/\s+/)
      .map((s) => s.trim())
      .filter(Boolean);

    (base as unknown as { command?: string }).command = values.command || undefined;
    (base as unknown as { args?: string[] | null }).args = parsedArgs.length ? parsedArgs : null;
    (base as unknown as { cwd?: string | null }).cwd = values.cwd ?? null;
    (base as unknown as { env?: Record<string, unknown> | null }).env =
      ((initial as unknown as { env?: Record<string, unknown> | null }).env ?? null) || null;
  }

  return base;
}

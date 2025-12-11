import type { MCPServer, MCPServerEdit } from '~/queries/mcpServers';
import { ListPlatformsResponse } from '~/queries/platforms';
import { UserTenant } from '~/queries/tenants';
import type { MCPHeaderValue } from '~/routes/tenants/$tenantId/agents/deploy/components/context';
import { getBasePath } from '~/utils/base';

export const snakeCaseToCamelCase = (str: string): string => {
  return str
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

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

export const getAlowedModelFromPlatform = (platform: ListPlatformsResponse[number]) => {
  // The allow list in platform.models is a map from <provider>: [<model1>, <model2>, ...]
  // We set this up with the flexibility to allow _more than a single model_ across _many providers_
  // in a platform (say use either OpenAI's gpt-5 or Anthropic's claude-4-5 on the Cortex platform)
  const allowedProviders = Object.keys(platform.models ?? {});
  const allowedModels = allowedProviders.flatMap((provider) => platform.models?.[provider] ?? []);
  // Shouldn't be possible, but just in case
  if (allowedModels.length === 0) {
    return 'unknown';
  }
  // Today, however, we almost solely construct platforms pinned to a single mode from a single provider
  if (allowedModels.length === 1) {
    return allowedModels[0];
  }
  // Shouldn't hit this, but if we do, return something reasonable
  return allowedModels.join(', ');
};

export const beautifyLabel = (value: string): string => {
  const id = value.split(':')[1] || value;
  return (
    id
      .replace(/-/g, ' ')
      .replace(/^gpt /, 'GPT-')
      .replace(/^claude /, 'Claude ')
      .replace(/^o(\d)/i, (_, d) => `O${d} `)
      .replace(/\bmini\b/i, 'Mini')
      .replace(/\bhigh\b/i, '(High)')
      .replace(/\bmedium\b/i, '(Medium)')
      .replace(/\blow\b/i, '(Low)')
      .replace(/\bminimal\b/i, '(Minimal)')
      .replace(/\bnone\b/i, '(None)')
      .replace(/\bxhigh\b/i, '(Extra-High)')
      .replace(/\bopenai service\b/i, 'OpenAI Service')
      .replace(/\bamazon bedrock\b/i, 'Amazon Bedrock')
      .replace(/\bazure\b/i, 'Azure')
      .replace(/\bopenai\b/i, 'OpenAI')
      .replace(/\bbedrock\b/i, 'Bedrock')
      .replace(/\cortex\b/i, 'Cortex')
      // Digit space digit -> digit.digit
      .replace(/\b(\d) (\d)\b/g, '$1.$2')
      .replace(/\b(\w)/g, (m) => m.toUpperCase())
  );
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

type HeaderEntry = { key: string; value?: string; type: MCPHeaderValue['type'] };

function entriesToHeaders(
  entries: HeaderEntry[] | undefined | null,
): Record<string, string | { type: 'secret'; value: string }> {
  const out: Record<string, string | { type: 'secret'; value: string }> = {};
  for (const { key, value = '', type } of entries || []) {
    if (!key || key.trim().length === 0) continue;
    out[key] = type === 'secret' ? { type: 'secret', value } : value;
  }
  return out;
}

export function headersToEntries(
  headers?: Record<string, string | { type?: string; value?: string } | undefined> | null,
): HeaderEntry[] {
  if (!headers) return [];
  return Object.entries(headers).map(([key, value]) => {
    if (value && typeof value === 'object' && (value as { type?: string }).type?.toLowerCase() === 'secret') {
      return { key, value: (value as { value?: string }).value ?? '', type: 'secret' };
    }
    return { key, value: (value as string | undefined) ?? '', type: 'string' };
  });
}

export function mcpHeadersFromRecord(
  headers?: Record<string, MCPHeaderValue | string | null> | null,
): Record<string, string | { type: 'secret'; value: string }> | undefined {
  if (!headers) return undefined;
  const out: Record<string, string | { type: 'secret'; value: string }> = {};
  for (const [key, raw] of Object.entries(headers)) {
    if (!key || key.trim().length === 0) continue;
    if (raw && typeof raw === 'object' && 'type' in (raw as MCPHeaderValue)) {
      const v = raw as MCPHeaderValue;
      out[key] = v.type === 'secret' ? { type: 'secret', value: v.value ?? '' } : (v.value ?? '');
    } else {
      out[key] = (raw as string | undefined) ?? '';
    }
  }
  return Object.keys(out).length ? out : undefined;
}

export function buildUpdateMcpBody(
  values: {
    name: string;
    type: MCPServerEdit['type'];
    transport: MCPServerEdit['transport'];
    url?: string;
    headerEntries?: HeaderEntry[];
    command?: string;
    argsText?: string;
    cwd?: string;
  },
  initial: MCPServer,
): MCPServerEdit {
  const headers = entriesToHeaders(values.headerEntries);
  const base: MCPServerEdit = {
    name: values.name,
    type: values.type ?? 'generic_mcp',
    transport: values.transport,
    url: values.transport === 'stdio' ? null : values.url || null,
    headers: Object.keys(headers).length ? (headers as MCPServerEdit['headers']) : null,
  } as MCPServerEdit;

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

export const downloadJSON = (
  data: unknown,
  options: {
    filename: string;
    addTimestamp?: boolean;
  },
): void => {
  const { filename, addTimestamp = false } = options;

  const dataToDownload = addTimestamp ? { ...(data as object), exportedAt: new Date().toISOString() } : data;

  const blob = new Blob([JSON.stringify(dataToDownload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.json') ? filename : `${filename}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

import { UserTenant } from '~/queries/tenants';
import { getBasePath } from '~/utils/base';
import type { MCPServerCreate, MCPServer, MCPServerEdit } from '~/queries/mcpServers';
import type { MCPHeaderValue } from '~/routes/tenants/$tenantId/agents/deploy/components/context';
import { Scenario, Trial } from '~/queries/evals';
import { components } from '@sema4ai/agent-server-interface';

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

type HeaderEntry = { key: string; value?: string; type: MCPHeaderValue['type'] };

export function entriesToHeaders(
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

export function buildCreateMcpBody(values: {
  name: string;
  type: MCPServerCreate['type'];
  transport: MCPServerCreate['transport'];
  url?: string;
  headerEntries?: HeaderEntry[];
}): MCPServerCreate {
  const headers = entriesToHeaders(values.headerEntries);
  return {
    name: values.name,
    type: values.type ?? 'generic_mcp',
    transport: values.transport,
    url: values.url || undefined,
    headers: Object.keys(headers).length ? (headers as MCPServerCreate['headers']) : undefined,
  } as MCPServerCreate;
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

export const transformAgentServerScenarios = (
  scenarios: Scenario[],
  latestRunsData: (components['schemas']['ScenarioRun'] | null)[],
) => {
  return scenarios.map((apiScenario, index) => {
    const latestRunQuery = latestRunsData[index];

    const isRunning =
      latestRunQuery?.trials?.some((trial: Trial) => trial.status === 'PENDING' || trial.status === 'EXECUTING') ??
      false;

    return {
      scenario: {
        scenarioId: apiScenario.scenario_id,
        name: apiScenario.name,
        description: apiScenario.description,
        threadId: apiScenario.thread_id,
        messages: apiScenario.messages,
      },
      latestRun: latestRunQuery
        ? {
            scenarioRunId: latestRunQuery.scenario_run_id,
            scenarioId: latestRunQuery.scenario_id,
            numTrials: latestRunQuery.num_trials,
            trials:
              latestRunQuery.trials?.map((trial: Trial) => ({
                trialId: trial.trial_id,
                status: trial.status,
                errorMessage: trial.error_message ?? null,
                threadId: trial.thread_id ?? null,
                statusUpdatedAt: trial.status_updated_at ?? null,
                evaluationResults:
                  trial.evaluation_results?.map((result) => ({
                    kind: result.kind as 'response_accuracy' | 'flow_adherence' | 'action_calling',
                    passed: result.passed,
                    score: 'score' in result ? result.score : undefined,
                    explanation: 'explanation' in result ? result.explanation : undefined,
                    issues: 'issues' in result ? result.issues : undefined,
                  })) || [],
              })) || [],
          }
        : null,
      isRunning,
    };
  });
};

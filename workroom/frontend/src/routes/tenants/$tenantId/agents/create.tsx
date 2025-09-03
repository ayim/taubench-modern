import type { components, operations } from '@sema4ai/agent-server-interface';
import { useMutation } from '@tanstack/react-query';
import {
  createFileRoute,
  Outlet,
  useLoaderData,
  useNavigate,
  useParams,
  useRouteContext,
} from '@tanstack/react-router';
import { useState } from 'react';
import { errorToast, successToast } from '~/utils/toasts';
import { AgentDeploymentForm } from './create/components/AgentDeploymentForm';
import type { AgentPackageResponse } from './create/components/AgentUploadForm';
import { AgentUploadForm } from './create/components/AgentUploadForm';
import { AgentDeploymentFormSchema } from './create/components/context';

export const Route = createFileRoute('/tenants/$tenantId/agents/create')({
  component: CreateAgentIndex,
});

type AgentPackagePayload = components['schemas']['AgentPackagePayload'];

async function buildAgentPackagePayload(
  form: AgentDeploymentFormSchema,
  options: { packageBase64?: string; packageUrl?: string; includeMcpServers?: boolean } = {},
  deps?: {
    fetchPlatformById: (
      platformId: string,
    ) => Promise<{ kind?: string; name?: string; models?: Record<string, string[]> } | undefined>;
  },
): Promise<AgentPackagePayload> {
  const { packageBase64, packageUrl } = options;

  // TODO: Change `type` when we have a form to use and change it.
  const mcpServers = (form.mcpServerSettings ?? []).map((s) => ({
    name: s.name,
    type: 'generic_mcp' as const,
    transport: s.transport,
    url: s.url ?? null,
    headers: s.headers ?? undefined,
    force_serial_tool_calls: s.force_serial_tool_calls,
  }));

  const buildModel = async (): Promise<Record<string, unknown> | undefined> => {
    const raw = form.llmId;
    const toTitle = (s: string) => (s ? s[0].toUpperCase() + s.slice(1).toLowerCase() : s);

    // ZIP-suggested model
    if (typeof raw === 'string' && raw.startsWith('package:')) {
      const [, providerRaw, modelNameRaw] = raw.split(':');
      const providerId = (providerRaw || '').toLowerCase();
      const modelName = modelNameRaw || '';
      // Legacy backend expects Title-cased provider names for conversion
      const provider = (() => {
        if (providerId === 'openai') return 'OpenAI';
        if (providerId === 'azure') return 'Azure';
        if (providerId === 'anthropic') return 'Anthropic';
        if (providerId === 'bedrock' || providerId === 'amazon') return 'Amazon';
        if (providerId === 'snowflake' || providerId === 'cortex') return 'Snowflake Cortex AI';
        return toTitle(providerId);
      })();

      const config: Record<string, unknown> = { temperature: 1 };
      if (form.apiKey) {
        const keyField = (() => {
          if (providerId === 'openai') return 'openai_api_key';
          if (providerId === 'google' || providerId === 'gemini') return 'google_api_key';
          if (providerId === 'anthropic') return 'anthropic_api_key';
          if (providerId === 'groq') return 'groq_api_key';
          return 'api_key';
        })();
        config[keyField] = form.apiKey;
      }
      return { provider, name: modelName, config } as Record<string, unknown>;
    }

    // Saved platform selected: include provider + a representative model name
    if (typeof raw === 'string' && deps?.fetchPlatformById) {
      const plat = await deps.fetchPlatformById(raw);
      if (!plat) return undefined;
      const providerId = (plat.kind || '').toLowerCase();
      // Legacy backend expects Title-cased provider names for conversion
      const provider = (() => {
        if (providerId === 'openai') return 'OpenAI';
        if (providerId === 'azure') return 'Azure';
        if (providerId === 'anthropic') return 'Anthropic';
        if (providerId === 'bedrock' || providerId === 'amazon') return 'Amazon';
        if (providerId === 'snowflake' || providerId === 'cortex') return 'Snowflake Cortex AI';
        return toTitle(providerId);
      })();
      const firstModel = (plat.models?.[providerId] || [])[0] || '';
      if (!provider || !firstModel) return undefined;

      const config: Record<string, unknown> = { temperature: 1 };
      const platAny = plat as Record<string, unknown>;

      const getFromPlat = (key: string): unknown => {
        const normalizeSecretish = (val: unknown): string | undefined => {
          if (typeof val === 'string') return val;
          if (val && typeof val === 'object' && 'value' in (val as Record<string, unknown>)) {
            const inner = (val as { value?: unknown }).value;
            if (typeof inner === 'string') return inner;
          }
          return undefined;
        };

        const directRaw = platAny[key];
        const direct = normalizeSecretish(directRaw);
        if (direct && direct !== 'UNSET' && direct !== '**********') return direct;

        const creds = platAny.credentials as Record<string, unknown> | undefined;
        if (creds) {
          const nestedRaw = creds[key];
          const nested = normalizeSecretish(nestedRaw);
          if (nested && nested !== 'UNSET' && nested !== '**********') return nested;
        }

        return undefined;
      };

      // Primary API key per provider
      const credentialKey = (() => {
        if (providerId === 'openai') return 'openai_api_key';
        if (providerId === 'google' || providerId === 'gemini') return 'google_api_key';
        if (providerId === 'anthropic' || providerId === 'claude') return 'anthropic_api_key';
        if (providerId === 'groq') return 'groq_api_key';
        if (providerId === 'azure') return 'azure_api_key';
        if (providerId === 'bedrock' || providerId === 'amazon') return 'aws_secret_access_key';
        return 'api_key';
      })();
      const primary = getFromPlat(credentialKey);
      if (typeof primary === 'string') {
        config[credentialKey] = primary;
      }

      if (providerId === 'azure') {
        const azureKeys = ['azure_endpoint_url', 'azure_api_version', 'azure_deployment_name'] as const;
        for (const k of azureKeys) {
          const v = getFromPlat(k);
          if (typeof v === 'string') config[k] = v;
        }
      }
      if (providerId === 'bedrock' || providerId === 'amazon') {
        const bedrockKeys = ['aws_access_key_id', 'aws_secret_access_key', 'region_name'] as const;
        for (const k of bedrockKeys) {
          const v = getFromPlat(k);
          if (typeof v === 'string') config[k] = v;
        }
      }

      return { provider, name: firstModel, config } as Record<string, unknown>;
    }

    return undefined;
  };

  const modelForPayload = await buildModel();

  const payload = {
    name: form.name,
    ...(form.description ? { description: form.description } : {}),
    public: true,
    ...(packageUrl ? { agent_package_url: packageUrl } : {}),
    ...(packageBase64 ? { agent_package_base64: packageBase64 } : {}),
    ...(modelForPayload ? { model: modelForPayload } : {}),
    action_servers: [],
    ...(options.includeMcpServers && mcpServers.length ? { mcp_servers: mcpServers } : {}),
  } satisfies AgentPackagePayload;

  return payload;
}

function CreateAgentIndex() {
  const [uploadedAgentPackage, setUploadedAgentPackage] = useState<{
    file: File;
    fileContent: AgentPackageResponse;
  } | null>(null);
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/create' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const navigate = useNavigate();
  const isDryRun = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('dryRun') === '1';

  const deployMutation = useMutation({
    mutationFn: async (payload: AgentDeploymentFormSchema) => {
      if (!uploadedAgentPackage) {
        throw new Error('Provide a package file to upload');
      }

      const jsonPayload = await buildAgentPackagePayload(
        payload,
        {
          packageBase64: undefined,
          packageUrl: undefined,
          includeMcpServers: true,
        },
        {
          fetchPlatformById: async (platformId: string) => {
            try {
              return (await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/{platform_id}', {
                params: { path: { platform_id: platformId } },
                silent: true,
              })) as { kind?: string; name?: string; models?: Record<string, string[]> };
            } catch {
              return undefined;
            }
          },
        },
      );

      const formData = new FormData();
      formData.append('package_zip_file', uploadedAgentPackage.file, uploadedAgentPackage.file.name);
      const serialize = (value: unknown): string => {
        if (value === null) return '';
        if (typeof value === 'string') return value;
        if (typeof value === 'number' || typeof value === 'boolean') return String(value);
        return JSON.stringify(value);
      };
      for (const [key, value] of Object.entries(jsonPayload)) {
        if (value === undefined) continue;
        formData.append(key, serialize(value));
      }

      const response = (await agentAPIClient.deployAgentFromPackageMultipart(
        tenantId,
        formData,
      )) as operations['deploy_agent_from_package_package_deploy_agent_post']['responses'][200]['content']['application/json'];
      return response;
    },
    onSuccess: (response) => {
      successToast('Agent created successfully');
      const agentId =
        (response as { agent_id?: string | null; id?: string | null }).agent_id ??
        (response as { id?: string | null }).id;
      if (agentId) {
        navigate({ to: '/tenants/$tenantId/$agentId', params: { tenantId, agentId } });
      }
    },
    onError: (err: unknown) => {
      errorToast(err instanceof Error ? err.message : 'Failed to create agent');
    },
  });

  const onUploadSuccess = ({ file, extracted }: { file: File; extracted: AgentPackageResponse }) => {
    setUploadedAgentPackage({ file, fileContent: extracted });
  };

  const onSubmit = async (payload: AgentDeploymentFormSchema) => {
    if (!uploadedAgentPackage) {
      errorToast('Provide a package file to upload');
      return;
    }
    if (isDryRun) {
      successToast('Dry run: payload logged. Skipping deploy.');
      return;
    }
    await deployMutation.mutateAsync(payload);
  };

  const { agents } = useLoaderData({ from: '/tenants/$tenantId' });
  const existingAgentNames = agents.map((agent) => agent.name);

  const shouldShowUploadForm = uploadedAgentPackage === null;

  if (shouldShowUploadForm) {
    return (
      <>
        <AgentUploadForm onSuccess={onUploadSuccess} />
        <Outlet />
      </>
    );
  }

  return (
    <>
      <AgentDeploymentForm
        agentTemplate={uploadedAgentPackage.fileContent.agentTemplate}
        defaultValues={uploadedAgentPackage.fileContent.defaultValues}
        onSubmit={onSubmit}
        isPending={deployMutation.isPending}
        title="Create Agent"
        existingAgentNames={existingAgentNames}
      />
      <Outlet />
    </>
  );
}

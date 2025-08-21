import { createFileRoute, useNavigate, useParams, useRouteContext } from '@tanstack/react-router';
import { useState } from 'react';
import { Box, Dropzone, Typography } from '@sema4ai/components';
import { successToast, errorToast } from '~/utils/toasts';
import { AgentDeploymentFormSchema, MCPServerSettings } from './components/context';
import { AgentDeploymentForm } from './components/AgentDeploymentForm';

export const Route = createFileRoute('/tenants/$tenantId/agents/create/')({
  component: CreateAgentIndex,
});

// Types for package inspection + payload (local, until we move to shared types)
type AgentPackageResponse = {
  agentTemplate: {
    id: string;
    name: string;
    description: string;
    metadata: { mode: 'worker' | 'conversational' };
    actions: Array<{ id: string; name: string }>;
    mcpServers: Array<{
      config: {
        name: string;
        url: string;
        transport: 'sse' | 'streamable-http';
        headers: unknown;
        tools?: Array<{ name: string; icon?: string }>;
      };
    }>;
    dataSources: Array<{ id: string; engine: string; name: string }>;
  };
  defaultValues: AgentDeploymentFormSchema;
};

type AgentPackagePayload = {
  name: string;
  description?: string | null;
  public: boolean;
  agent_package_url?: string;
  agent_package_base64?: string;
  model?: Record<string, unknown>;
  action_servers?: Array<{ url: string; api_key: string | { value: string } }>;
  mcp_servers?: Array<{
    name: string;
    transport: 'auto' | 'sse' | 'streamable-http' | 'stdio';
    url?: string | null;
    headers?: Record<string, unknown> | null;
    command?: string;
    args?: string[];
    env?: Record<string, unknown>;
    cwd?: string;
  }>;
  langsmith?: null | {
    api_key?: string | { value: string };
    api_url?: string;
    project_name?: string;
  };
};

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(',')[1] ?? result);
    };
    reader.onerror = (e) => reject(e);
    reader.readAsDataURL(file);
  });
}

function buildAgentPackagePayload(
  form: AgentDeploymentFormSchema,
  options: { packageBase64?: string; packageUrl?: string; includeMcpServers?: boolean } = {},
): AgentPackagePayload {
  const { packageBase64, packageUrl } = options;

  const mapMcpHeadersToStringMap = (headers: MCPServerSettings['headers']): Record<string, string> | undefined => {
    if (!headers) return undefined;
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(headers)) {
      const inner = (value as { value?: { type?: string; value?: string } } | undefined)?.value;
      out[key] = inner && inner.type === 'string' && typeof inner.value === 'string' ? inner.value : '';
    }
    return out;
  };

  const mcpServers: NonNullable<AgentPackagePayload['mcp_servers']> = (form.mcpServerSettings ?? []).map((s) => ({
    name: s.name,
    transport: s.transport,
    url: s.url ?? '',
    headers: mapMcpHeadersToStringMap(s.headers) ?? {},
    force_serial_tool_calls: false,
  }));

  const buildModel = () => {
    const config: Record<string, unknown> = { temperature: 1 };
    if (form.apiKey) {
      config.openai_api_key = form.apiKey;
    }
    // Temporary: hardcode OpenAI gpt-4o until dropdown mapping is finalized
    return { provider: 'OpenAI', name: 'gpt-4o', config } as Record<string, unknown>;
  };

  const payload: AgentPackagePayload = {
    name: form.name,
    ...(form.description ? { description: form.description } : {}),
    public: true,
    ...(packageUrl ? { agent_package_url: packageUrl } : {}),
    ...(packageBase64 ? { agent_package_base64: packageBase64 } : {}),
    model: buildModel(),
    action_servers: [],
    // Temporarily omit mcp_servers from deploy payload to avoid server-side dataclass conversion issues
    ...(options.includeMcpServers && mcpServers.length ? { mcp_servers: mcpServers } : {}),
    // Omit langsmith unless we have values; schema shows object, but optional
  };

  return payload;
}

// No mock data; wizard is shown only after successful inspection

// Type for the extracted agent package data
// Type is now imported from api-utils as AgentPackageResponse

function CreateAgentIndex() {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [extractedData, setExtractedData] = useState<AgentPackageResponse | null>(null);
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/create/' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const navigate = useNavigate();

  const onDrop = async (files: File[]) => {
    const file = files[0];
    if (!file) return;

    // Validate file type
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('File type is not valid. Only ZIP files are allowed.');
      return;
    }

    setError(undefined);
    setUploadedFile(file);
    setIsProcessing(true);

    try {
      const formData = new FormData();
      formData.append('package_zip_file', file, file.name);
      formData.append('name', file.name.replace(/\.zip$/i, ''));
      formData.append('description', 'Package uploaded from UI');

      const inspectResponseJson = await agentAPIClient.inspectAgentPackageViaGateway(tenantId, formData);

      // Map inspect response to wizard data
      const status = (inspectResponseJson as { status?: string }).status;
      const data = (inspectResponseJson as { data?: Record<string, unknown> }).data as
        | {
            name?: string;
            description?: string;
            metadata?: { mode?: 'worker' | 'conversational' };
            mcp_servers?: Array<{
              name?: string;
              transport?: 'sse' | 'streamable-http' | 'auto' | 'stdio';
              url?: string;
              headers?: Record<string, unknown>;
            }>;
            datasources?: Array<{ engine?: string; customer_facing_name?: string }>;
          }
        | undefined;

      if (status === 'success' && data) {
        const mcpServers = (data.mcp_servers ?? []).map((srv, idx) => ({
          config: {
            name: srv.name ?? `MCP ${idx + 1}`,
            url: srv.url ?? '',
            transport: (srv.transport === 'sse' || srv.transport === 'streamable-http'
              ? srv.transport
              : 'streamable-http') as 'sse' | 'streamable-http',
            headers: null,
            tools: [],
          },
        }));

        const agentTemplate: AgentPackageResponse['agentTemplate'] = {
          id: (data.name ?? 'inspected-template').toLowerCase().replace(/\s+/g, '-'),
          name: data.name ?? 'Inspected Agent',
          description: data.description ?? '',
          metadata: { mode: data.metadata?.mode === 'worker' ? 'worker' : 'conversational' },
          actions: [],
          mcpServers,
          dataSources: (data.datasources ?? []).map((ds, i) => ({
            id: `${ds.engine ?? 'source'}-${i}`,
            engine: ds.engine ?? 'unknown',
            name: ds.customer_facing_name ?? 'Datasource',
          })),
        };

        const defaultValues = {
          agentTemplateId: agentTemplate.id,
          actionDeploymentIds: [],
          actionIds: [],
          name: agentTemplate.name,
          description: agentTemplate.description,
          workspaceId: '',
          // Prefill an LLM; user can change. Our mock options expect one of mock keys.
          llmId: 'openai-gpt-5',
          apiKey: '',
          oAuthProviders: {},
          feedbackRecipients: [],
          langsmithIntegrationId: undefined,
          actionSettings: {},
          mcpServerSettings: mcpServers.map((s) => ({
            name: s.config.name,
            url: s.config.url,
            transport: s.config.transport === 'sse' ? 'sse' : 'streamable-http',
            headers: null,
          })),
          documentWorkflowAssignment: null,
          dataSources: [],
        } satisfies AgentDeploymentFormSchema;

        setExtractedData({ agentTemplate, defaultValues });
        setShowWizard(true);
      } else {
        setError('Failed to process agent package. Please check the file format.');
      }

      setIsProcessing(false);
    } catch (error) {
      console.error('❌ Error processing ZIP file:', error);
      setError('Failed to process agent package. Please check the file format.');
      setIsProcessing(false);
    }
  };

  const onSubmit = async (payload: AgentDeploymentFormSchema) => {
    try {
      let response: unknown;
      if (uploadedFile) {
        const base64 = await fileToBase64(uploadedFile);
        const jsonPayload = buildAgentPackagePayload(payload, {
          packageBase64: base64,
          packageUrl: undefined,
          // Backend now supports MCP server conversion; include them in deploy payload
          includeMcpServers: true,
        }) as unknown as Record<string, unknown>;
        response = await agentAPIClient.deployAgentFromPackage(tenantId, jsonPayload);
      } else {
        // If no file was uploaded, require a valid URL (none provided here)
        errorToast('Provide a package file to upload');
        return;
      }

      successToast('Agent created successfully');

      // Navigate to the created agent page (use agent_id or fallback to id)
      const created = response as unknown as { agent_id?: string; id?: string };
      const agentId = created?.agent_id ?? created?.id;
      if (agentId) {
        navigate({ to: '/tenants/$tenantId/$agentId', params: { tenantId, agentId } });
      }
    } catch (err) {
      console.error('❌ Deployment failed:', err);
      errorToast(err instanceof Error ? err.message : 'Failed to create agent');
      throw err;
    }
  };

  if (!showWizard) {
    return (
      <div className="h-full overflow-x-hidden">
        <div className="mx-12 my-10">
          <div className="flex flex-col h-full overflow-auto">
            {/* Header matching Agents page */}
            <header className="text-center">
              <div className="flex items-center justify-center gap-2 !mb-2 h-11">
                <img src="svg/IconAgentsPage.svg" className="h-full" />
                <Typography
                  lineHeight="29px"
                  fontFamily="Heldane Display"
                  fontWeight="500"
                  as="h1"
                  className="text-[2.5rem]"
                >
                  Create Agent
                </Typography>
              </div>
              <p className="text-sm">Upload an agent package to get started with deployment.</p>
            </header>

            {/* File Drop Area */}
            <Box className="border border-solid bg-white border-[#CDCDCD] rounded-[10px] p-8 flex-grow my-8">
              <div className="flex justify-center items-center h-full">
                <Box width="100%" maxWidth={720}>
                  <Dropzone
                    onDrop={onDrop}
                    title={isProcessing ? 'Processing...' : 'Drop your package here'}
                    dropTitle={isProcessing ? 'Processing agent package...' : 'Drop Files to Upload'}
                    description={
                      isProcessing
                        ? 'Please wait while we process your agent package...'
                        : 'Upload a .zip file containing the code for an agent that follows the agent structure guidelines.'
                    }
                    error={error}
                    disabled={isProcessing}
                  />
                  {uploadedFile && !isProcessing && (
                    <Box mt="$16" textAlign="center">
                      <p>Uploaded: {uploadedFile.name}</p>
                    </Box>
                  )}
                </Box>
              </div>
            </Box>
          </div>
        </div>
      </div>
    );
  }

  return (
    <AgentDeploymentForm
      agentTemplate={extractedData!.agentTemplate}
      defaultValues={extractedData!.defaultValues}
      onSubmit={onSubmit}
      isPending={false}
      title="Create Agent"
    />
  );
}

import { FC } from 'react';
import { Box, Dropzone, Typography } from '@sema4ai/components';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import type { AgentDeploymentFormSchema } from './context';

export type LLMFromIntrospection = {
  provider: 'OpenAI';
  name:
    | 'gpt-4o'
    | 'gpt-3.5-turbo-1106'
    | 'gpt-4-turbo'
    | 'gpt-4-1'
    | 'gpt-4-1-mini'
    | 'o3-low'
    | 'o3-high'
    | 'o4-mini-high';
};

export type AgentPackageResponse = {
  agentTemplate: {
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
      };
    }>;
    dataSources: Array<{ id: string; engine: string; name: string }>;
    model: LLMFromIntrospection;
  };
  defaultValues: AgentDeploymentFormSchema;
};

type Props = {
  onSuccess: (result: { file: File; extracted: AgentPackageResponse }) => void;
};

export const AgentUploadForm: FC<Props> = ({ onSuccess }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/deploy' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  const schema = z.object({
    file: z
      .instanceof(File, { message: 'Please choose a file' })
      .refine((f) => f.name.toLowerCase().endsWith('.zip'), 'File type is not valid. Only ZIP files are allowed.'),
  });

  type FormValues = z.infer<typeof schema>;

  const {
    setValue,
    trigger,
    setError,
    watch,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), mode: 'onChange' });

  const inspectMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      return agentAPIClient.inspectAgentPackageViaGateway(tenantId, formData);
    },
  });

  const onDrop = async (files: File[]) => {
    const file = files[0];
    if (!file) return;

    setValue('file', file, { shouldValidate: true });
    const valid = await trigger('file');
    if (!valid) return;

    try {
      const formData = new FormData();
      formData.append('package_zip_file', file, file.name);
      formData.append('name', file.name.replace(/\.zip$/i, ''));
      formData.append('description', 'Package uploaded from UI');

      const inspectResponseJson = await inspectMutation.mutateAsync(formData);

      const status = (inspectResponseJson as { status?: string }).status;
      const data = (inspectResponseJson as { data?: Record<string, unknown> }).data as
        | {
            name: string;
            description?: string;
            metadata?: { mode?: 'worker' | 'conversational' };
            mcp_servers?: Array<{
              name?: string;
              transport?: 'sse' | 'streamable-http' | 'auto' | 'stdio';
              url?: string;
              type?: 'generic_mcp' | 'sema4ai_action_server';
              headers?: Record<string, unknown>;
            }>;
            datasources?: Array<{ engine?: string; customer_facing_name?: string }>;
            model: LLMFromIntrospection;
          }
        | undefined;

      if (status === 'success' && data) {
        const mcpServers = (data.mcp_servers ?? []).map((srv, idx) => ({
          config: {
            name: srv.name ?? `MCP ${idx + 1}`,
            type: srv.type ?? 'generic_mcp',
            url: srv.url ?? '',
            transport: (srv.transport === 'sse' || srv.transport === 'streamable-http'
              ? srv.transport
              : 'streamable-http') as 'sse' | 'streamable-http',
            headers: null,
            tools: [],
          },
        }));

        const agentTemplate: AgentPackageResponse['agentTemplate'] = {
          name: data.name,
          description: data.description ?? '',
          metadata: { mode: data.metadata?.mode === 'worker' ? 'worker' : 'conversational' },
          actions: [],
          mcpServers,
          dataSources: (data.datasources ?? []).map((ds, i) => ({
            id: `${ds.engine ?? 'source'}-${i}`,
            engine: ds.engine ?? 'unknown',
            name: ds.customer_facing_name ?? 'Datasource',
          })),
          model: data.model,
        };

        const defaultValues: AgentDeploymentFormSchema = {
          name: agentTemplate.name,
          description: agentTemplate.description,
          llmId: '',
          apiKey: '',
          mcpServerSettings: mcpServers.map((s) => ({
            name: s.config.name,
            type: s.config.type,
            url: s.config.url,
            transport: s.config.transport === 'sse' ? 'sse' : 'streamable-http',
            headers: null,
            command: null,
            args: null,
            env: null,
            cwd: null,
            force_serial_tool_calls: false,
          })),
        };

        const extracted: AgentPackageResponse = { agentTemplate, defaultValues };
        onSuccess({ file, extracted });
      } else {
        setError('file', {
          type: 'server',
          message: 'Failed to process agent package. Please check the file format.',
        });
      }
    } catch (err) {
      console.error('❌ Error processing ZIP file:', err);
      setError('file', {
        type: 'server',
        message: 'Failed to process agent package. Please check the file format.',
      });
    }
  };

  return (
    <>
      <div className="h-full overflow-x-hidden">
        <div className="mx-12 my-10">
          <div className="flex flex-col h-full overflow-auto">
            <header className="text-center">
              <div className="flex items-center justify-center gap-2 !mb-2 h-11">
                <img src="/svg/IconAgentsPage.svg" className="h-full" />
                <Typography
                  lineHeight="29px"
                  fontFamily="Heldane Display"
                  fontWeight="500"
                  as="h1"
                  className="text-[2.5rem]"
                >
                  Deploy Agent
                </Typography>
              </div>
              <p className="text-sm">Upload an agent package to get started with deployment.</p>
            </header>
            <Box className="border border-solid bg-white border-[#CDCDCD] rounded-[10px] p-8 flex-grow my-8">
              <div className="flex justify-center items-center h-full">
                <Box width="100%" maxWidth={720}>
                  <Dropzone
                    onDrop={onDrop}
                    title={inspectMutation.isPending ? 'Processing...' : 'Drop your package here'}
                    dropTitle={inspectMutation.isPending ? 'Processing agent package...' : 'Drop Files to Upload'}
                    description={
                      inspectMutation.isPending
                        ? 'Please wait while we process your agent package...'
                        : 'Upload a .zip file containing the code for an agent that follows the agent structure guidelines.'
                    }
                    error={
                      errors.file?.message ||
                      (inspectMutation.error instanceof Error ? inspectMutation.error.message : undefined)
                    }
                    disabled={inspectMutation.isPending}
                  />
                  {watch('file') && !inspectMutation.isPending && (
                    <Box mt="$16" textAlign="center">
                      <p>Uploaded: {watch('file')?.name}</p>
                    </Box>
                  )}
                </Box>
              </div>
            </Box>
          </div>
        </div>
      </div>
    </>
  );
};

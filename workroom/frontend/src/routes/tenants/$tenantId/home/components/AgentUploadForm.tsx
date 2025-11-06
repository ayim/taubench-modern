import { ReactNode } from 'react';
import { Box, Button, useSnackbar } from '@sema4ai/components';
import { useParams } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { FileRejection, useDropzone } from 'react-dropzone';
import type { AgentDeploymentFormSchema } from '../../agents/deploy/components/context';
import { IconPlus } from '@sema4ai/icons';
import { useUploadAgentPackageMutation } from '~/queries/agentPackageUpload';
import { useTenantContext } from '~/lib/tenantContext';
import { useInspectAgentPackageMutation } from '@sema4ai/spar-ui/queries';
import { useSparUIContext } from '@sema4ai/spar-ui';

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
    version: string;
    icon?: string;
    metadata: { mode: 'worker' | 'conversational' };
    mcpServers: Array<{
      config: {
        name: string;
        url: string;
        transport: 'sse' | 'streamable-http';
        headers: unknown;
      };
    }>;
    action_packages: Array<{
      name: string;
      description: string;
      action_package_version: string;
      actions?: Array<{
        name: string;
        description: string;
        summary: string;
      }>;
      icon?: ReactNode;
      queries?: Array<{
        name: string;
        description?: string;
      }>;
      mcpTools?: Array<{
        name: string;
        description?: string;
      }>;
    }>;
    dataSources: Array<{ id: string; engine: string; name: string }>;
    model: LLMFromIntrospection;
  };
  defaultValues: AgentDeploymentFormSchema;
};

export const AgentUploadForm = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { addSnackbar } = useSnackbar();
  const uploadAgentPackageMutation = useUploadAgentPackageMutation();
  const { sparAPIClient } = useSparUIContext();
  const inspectAgentPackageMutation = useInspectAgentPackageMutation({ sparAPIClient });
  const { features } = useTenantContext();

  const schema = z.object({
    file: z
      .instanceof(File, { message: 'Please choose a file' })
      .refine((f) => f.name.toLowerCase().endsWith('.zip'), 'File type is not valid. Only ZIP files are allowed.'),
  });

  type FormValues = z.infer<typeof schema>;

  const { setValue, trigger } = useForm<FormValues>({ resolver: zodResolver(schema), mode: 'onChange' });

  const onDrop = async (files: File[], fileRejection: FileRejection[]) => {
    const file = files[0];

    const error = fileRejection?.[0]?.errors?.[0];
    if (error && error.message) {
      addSnackbar({
        message: error.message,
        variant: 'danger',
      });
      return;
    }

    if (!file) {
      return;
    }

    setValue('file', file, { shouldValidate: true });
    const valid = await trigger('file');
    if (!valid) return;

    try {
      const formData = new FormData();
      formData.append('package_zip_file', file, file.name);
      formData.append('name', file.name.replace(/\.zip$/i, ''));
      formData.append('description', 'Package uploaded from UI');

      const data = await inspectAgentPackageMutation.mutateAsync({ formData });

      const mcpServers = data.mcp_servers.map((srv) => ({
        config: {
          name: srv.name,
          type: srv.type,
          url: srv.url,
          transport: srv.transport as 'sse' | 'streamable-http',
          headers: srv.headers,
          tools: [],
        },
      }));

      const agentTemplate: AgentPackageResponse['agentTemplate'] = {
        name: data.name,
        description: data.description,
        metadata: { mode: data.metadata.mode },
        version: data.version,
        action_packages: data.action_packages,
        mcpServers,
        dataSources: data.datasources.map((ds, i) => ({
          id: `${ds.engine}-${i}`,
          engine: ds.engine,
          name: ds.customer_facing_name,
        })),
        model: data.model as LLMFromIntrospection,
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
        selected_tools:
          'selected_tools' in data &&
          data.selected_tools &&
          typeof data.selected_tools === 'object' &&
          'tool_names' in data.selected_tools
            ? (data.selected_tools as { tool_names: Array<{ tool_name: string }> })
            : { tool_names: [] },
      };

      const extracted: AgentPackageResponse = { agentTemplate, defaultValues };

      // Store the agent package data in React Query cache and navigate
      await uploadAgentPackageMutation.mutateAsync({
        tenantId,
        data: {
          file,
          fileContent: extracted,
        },
      });
    } catch (err) {
      console.error('❌ Error processing ZIP file:', err);
      addSnackbar({
        message: 'Failed to process agent package. Please check the file format.',
        variant: 'danger',
      });
    }
  };

  const { getInputProps, open } = useDropzone({
    multiple: false,
    accept: {
      'application/zip': ['.zip'],
    },
    maxSize: 100_000_000,
    onDrop: onDrop,

    // Disable click and keydown behavior since we're using a button
    noClick: true,
    noKeyboard: true,
  });

  return (
    <Box height="100%" display="flex" flexDirection="row" gap={2}>
      <input {...getInputProps()} />
      {features.deploymentWizard.enabled && (
        <Button icon={IconPlus} round onClick={open} loading={uploadAgentPackageMutation.isPending}>
          Agent
        </Button>
      )}
    </Box>
  );
};

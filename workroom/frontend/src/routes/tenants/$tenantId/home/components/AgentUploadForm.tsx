import { Box, Button, useSnackbar } from '@sema4ai/components';
import { useParams } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { FileRejection, useDropzone } from 'react-dropzone';
import { IconPlus } from '@sema4ai/icons';
import { useUploadAgentPackageMutation } from '~/queries/agentPackageUpload';
import { useTenantContext } from '~/lib/tenantContext';
import { useInspectAgentPackageMutation } from '@sema4ai/spar-ui/queries';
import { useSparUIContext } from '@sema4ai/spar-ui';

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

      const inspectionResult = await inspectAgentPackageMutation.mutateAsync({ formData });

      if (inspectionResult.status === 'failure' || !inspectionResult.data) {
        throw new Error('Failed to inspect agent package: no data returned');
      }

      const inspectionData = inspectionResult.data;

      const mcpServerSettings = (inspectionData.mcp_servers ?? []).map((srv) => ({
        name: srv.name,
        type: 'sema4ai_action_server' as const,
        transport: srv.transport,
        url: srv.url ?? null,
        headers: srv.headers
          ? Object.fromEntries(
              Object.entries(srv.headers).map(([key, val]) => [
                key,
                { type: val.type as 'string' | 'secret', description: val.description, value: val.value },
              ]),
            )
          : null,
        force_serial_tool_calls: srv.force_serial_tool_calls,
      }));

      await uploadAgentPackageMutation.mutateAsync({
        tenantId,
        data: {
          file,
          fileContent: {
            agentTemplate: inspectionData,
            defaultValues: {
              name: inspectionData.name,
              description: inspectionData.description,
              llmId: '',
              apiKey: '',
              mcpServerSettings,
              selected_tools: { tool_names: inspectionData.selected_tools?.tool_names ?? [] },
            },
          },
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

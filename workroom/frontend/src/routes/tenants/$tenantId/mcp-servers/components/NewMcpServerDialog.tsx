import { zodResolver } from '@hookform/resolvers/zod';
import {
  Banner,
  Box,
  Button,
  Dialog,
  Dropzone,
  Form,
  Input,
  Select,
  Typography,
  useSnackbar,
} from '@sema4ai/components';
import { IconLightBulb, IconPlus, IconTrash } from '@sema4ai/icons';
import { FC, useState } from 'react';
import { Controller, useFieldArray, useForm, FormProvider } from 'react-hook-form';
import { useParams } from '@tanstack/react-router';
import { useCreateMcpServerMutation, useCreateHostedMcpServerMutation } from '~/queries/mcpServers';
import { InputControlled } from '~/components/InputControlled';
import { ActionPackageItem } from './ActionPackageItem';
import { useInspectAgentPackageMutation } from '@sema4ai/spar-ui/queries';
import { useSparUIContext } from '@sema4ai/spar-ui';
import {
  newMcpServerFormSchema,
  NewMcpServerFormInput,
  NewMcpServerFormValues,
  buildCreateMcpServerPayload,
  mcpTypeSelectItemsWithHosted,
  mcpTransportSelectItems,
  headerTypeSelectItems,
} from '~/lib/mcpServersUtils';
import { components } from '@sema4ai/agent-server-interface';

type UploadState =
  | { type: 'pending_upload' }
  | { type: 'uploading'; file: { name: string } }
  | { type: 'uploaded'; file: { name: string } }
  | {
      type: 'introspection_succeeded';
      file: { name: string };
      data: components['schemas']['AgentPackageInspectionResponse'];
    }
  | { type: 'uploading_failed'; error: Error }
  | { type: 'introspection_failed'; error: Error };

export const NewMcpServerDialog: FC<{ open: boolean; onClose: () => void }> = ({ open, onClose }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const createMutation = useCreateMcpServerMutation();
  const createHostedMutation = useCreateHostedMcpServerMutation();
  const { sparAPIClient } = useSparUIContext();
  const inspectAgentPackageMutation = useInspectAgentPackageMutation({ sparAPIClient });
  const form = useForm<NewMcpServerFormInput, unknown, NewMcpServerFormValues>({
    resolver: zodResolver(newMcpServerFormSchema),
    defaultValues: {
      name: '',
      type: 'generic_mcp',
      transport: 'auto',
      url: '',
      headersKV: [],
      agentPackageFile: undefined,
      agentPackageSecrets: {},
    },
    mode: 'onChange',
  });
  const { addSnackbar } = useSnackbar();
  const [uploadState, setUploadState] = useState<UploadState>({ type: 'pending_upload' });

  const headersArray = useFieldArray({ control: form.control, name: 'headersKV' as const });
  const typeValue = form.watch('type');
  const agentPackageFile = form.watch('agentPackageFile');

  const onDrop = async (files: File[]) => {
    const file = files[0];

    if (!file) {
      return;
    }

    const isZip = file.name.toLowerCase().endsWith('.zip');
    if (!isZip) {
      setUploadState({
        type: 'uploading_failed',
        error: new Error('File type is not valid. Only ZIP files are allowed.'),
      });
      return;
    }

    setUploadState({ type: 'uploading', file: { name: file.name } });

    try {
      form.setValue('agentPackageFile', file, { shouldValidate: true });
      setUploadState({ type: 'uploaded', file: { name: file.name } });

      const formData = new FormData();
      formData.append('package_zip_file', file, file.name);
      formData.append('name', file.name.replace(/\.zip$/i, ''));
      formData.append('description', 'Agent package uploaded from UI');

      const inspectionResult = await inspectAgentPackageMutation.mutateAsync({ formData });

      if (inspectionResult.status === 'failure' || !inspectionResult.data) {
        setUploadState({
          type: 'introspection_failed',
          error: new Error('Failed to inspect agent package: no data returned'),
        });
        return;
      }

      const inspectionData = inspectionResult.data;

      setUploadState({
        type: 'introspection_succeeded',
        file: { name: file.name },
        data: inspectionData,
      });

      if (!form.getValues('name')) {
        form.setValue('name', `MCP server for ${inspectionData.name ?? ''}`);
      }
    } catch (err) {
      const error =
        err instanceof Error ? err : new Error('Failed to process agent package. Please check the file format.');
      setUploadState({ type: 'introspection_failed', error });
      addSnackbar({
        message: error.message,
        variant: 'danger',
      });
    }
  };

  const onSubmit = form.handleSubmit((values) => {
    const body = buildCreateMcpServerPayload(values);

    if (values.type === 'hosted' && values.agentPackageFile) {
      const mcpServerMetadata =
        uploadState.type === 'introspection_succeeded' && uploadState.data ? { ...uploadState.data } : undefined;

      createHostedMutation.mutate(
        {
          tenantId,
          name: body.name,
          file: values.agentPackageFile,
          headers: body.headers,
          mcpServerMetadata,
        },
        {
          onSuccess: () => {
            addSnackbar({ message: 'MCP server created', variant: 'success' });
            onClose();
          },
          onError: (e) =>
            addSnackbar({ message: e instanceof Error ? e.message : 'Failed to save MCP server', variant: 'danger' }),
        },
      );
    } else {
      createMutation.mutate(
        { tenantId, body },
        {
          onSuccess: () => {
            addSnackbar({ message: 'MCP server created', variant: 'success' });
            onClose();
          },
          onError: (e) =>
            addSnackbar({ message: e instanceof Error ? e.message : 'Failed to save MCP server', variant: 'danger' }),
        },
      );
    }
  });

  const mutation = typeValue === 'hosted' ? createHostedMutation : createMutation;

  return (
    <Dialog open={open} size="x-large" onClose={() => onClose()}>
      <Form onSubmit={onSubmit} busy={mutation.isPending}>
        <FormProvider {...form}>
          <Dialog.Header>
            <Dialog.Header.Title title="New MCP server" />
            <Dialog.Header.Description>Configure an MCP server for your workspace.</Dialog.Header.Description>
          </Dialog.Header>
          <Dialog.Content>
            <Form.Fieldset>
              <Box display="flex" flexDirection="column" gap="$16">
                <Input
                  label="MCP Server Name"
                  {...form.register('name')}
                  error={form.formState.errors.name?.message}
                  placeholder="Enter name"
                  autoFocus
                />
                <Controller
                  control={form.control}
                  name="type"
                  render={({ field }) => <Select label="Type" items={[...mcpTypeSelectItemsWithHosted]} {...field} />}
                />
                {typeValue !== 'hosted' && (
                  <>
                    <Controller
                      control={form.control}
                      name="transport"
                      render={({ field }) => (
                        <Select label="Transport" items={[...mcpTransportSelectItems]} {...field} />
                      )}
                    />
                    <Box style={{ gridColumn: '1 / -1' }}>
                      <Input
                        label="URL"
                        placeholder="URL"
                        {...form.register('url')}
                        error={form.formState.errors.url?.message}
                      />
                    </Box>

                    <Box>
                      <Box mb="$8">Headers</Box>
                      <Box display="grid" gap="$8">
                        {headersArray.fields.map((f, idx) => (
                          <Box
                            key={f.id}
                            display="grid"
                            style={{ gridTemplateColumns: '1fr 160px 1fr auto', gap: '0.5rem' }}
                          >
                            <Input
                              label="Header key"
                              placeholder="Key"
                              {...form.register(`headersKV.${idx}.key` as const)}
                            />
                            <Controller
                              control={form.control}
                              name={`headersKV.${idx}.type` as const}
                              render={({ field }) => (
                                <Select label="Type" items={[...headerTypeSelectItems]} {...field} />
                              )}
                            />
                            <InputControlled
                              fieldName={`headersKV.${idx}.value` as const}
                              label="Header value"
                              placeholder="Value"
                              type={
                                (form.getValues(`headersKV.${idx}.type` as const) || 'string') === 'secret'
                                  ? 'password'
                                  : 'text'
                              }
                            />
                            <Button
                              variant="ghost"
                              size="small"
                              icon={IconTrash}
                              aria-label="Remove header"
                              type="button"
                              onClick={() => headersArray.remove(idx)}
                            />
                          </Box>
                        ))}
                        <Button
                          variant="outline"
                          icon={IconPlus}
                          type="button"
                          onClick={() => headersArray.append({ key: '', value: '', type: 'string' })}
                        >
                          Add header
                        </Button>
                      </Box>
                    </Box>
                  </>
                )}
                {typeValue === 'hosted' && (
                  <Box p="$4" display="flex" flexDirection="column" gap="$12">
                    <Box display="flex" flexDirection="column" gap="$12">
                      <Typography fontWeight="medium">
                        {uploadState.type === 'introspection_succeeded' ? 'Action Packages' : 'Agent Package'}
                      </Typography>
                      {uploadState.type === 'pending_upload' && (
                        <>
                          <Dropzone
                            onDrop={onDrop}
                            title={
                              <span>
                                Drag & drop or{' '}
                                <Typography color="accent" as="span">
                                  select file
                                </Typography>{' '}
                                to upload
                              </span>
                            }
                            dropTitle="Drop your files here"
                            description={'Upload to validate your agent package • Only ZIP files • Max size: 100MB'}
                          />
                          <Box mt="$16">
                            <Banner
                              message="Why do I need to upload an agent package?"
                              description={
                                <span>
                                  The actions in this package will be deployed as tools in this new MCP server, ready
                                  for your agent to use.
                                </span>
                              }
                              icon={IconLightBulb}
                              variant="alert"
                            />
                          </Box>
                        </>
                      )}
                      {(uploadState.type === 'uploading_failed' || uploadState.type === 'introspection_failed') && (
                        <>
                          <Dropzone
                            onDrop={onDrop}
                            title={
                              <span>
                                Drag & drop or{' '}
                                <Typography color="accent" as="span">
                                  select file
                                </Typography>{' '}
                                to upload
                              </span>
                            }
                            dropTitle="Drop your files here"
                            description={'Upload to validate your agent package • Only ZIP files • Max size: 100MB'}
                            error={uploadState.error.message}
                          />
                          <Box mt="$16">
                            <Banner
                              message="Why do I need to upload an agent package?"
                              description={
                                <span>
                                  The actions in this package will be deployed as tools in this new MCP server, ready
                                  for your agent to use.
                                </span>
                              }
                              icon={IconLightBulb}
                              variant="alert"
                            />
                          </Box>
                        </>
                      )}
                      {form.formState.errors.agentPackageFile && (
                        <Box style={{ color: 'var(--color-danger)', fontSize: '0.875rem', marginTop: '0.5rem' }}>
                          {form.formState.errors.agentPackageFile.message}
                        </Box>
                      )}
                    </Box>

                    {uploadState.type === 'introspection_succeeded' &&
                      uploadState.data?.action_packages &&
                      uploadState.data?.action_packages.length > 0 && (
                        <Box display="grid" gap="$16" mt="$16">
                          {uploadState.data.action_packages?.map((actionPackage, idx) => (
                            <ActionPackageItem key={`${actionPackage.name}-${idx}`} actionPackage={actionPackage} />
                          ))}
                        </Box>
                      )}
                  </Box>
                )}
              </Box>
            </Form.Fieldset>
          </Dialog.Content>
          <Dialog.Actions>
            <Button
              variant="primary"
              type="submit"
              round
              loading={mutation.isPending}
              disabled={typeValue === 'hosted' && !agentPackageFile}
            >
              Create
            </Button>
            <Button variant="outline" type="button" round onClick={() => onClose()}>
              Cancel
            </Button>
          </Dialog.Actions>
        </FormProvider>
      </Form>
    </Dialog>
  );
};

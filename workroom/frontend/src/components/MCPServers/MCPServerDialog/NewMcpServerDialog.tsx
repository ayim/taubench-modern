import { FC, useCallback } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Banner, Box, Button, Dialog, Dropzone, Form, Input, Progress, Select, Typography } from '@sema4ai/components';
import { IconLightBulb, IconPlus, IconTrash } from '@sema4ai/icons';
import { Controller, useFieldArray, useForm, FormProvider } from 'react-hook-form';

import {
  useCreateMcpServerMutation,
  useCreateHostedMcpServerMutation,
  useValidateMcpServerCapabilitiesMutation,
  useHostedMcpUpload,
  UseHostedMcpUploadResult,
} from '~/queries/mcpServers';
import { MCPServerAuthFields } from '../MCPServerAuth';
import { ActionPackageItem } from '../ActionPackage';
import {
  newMcpServerFormSchema,
  headerTypeSelectItems,
  buildCreateMcpServerPayload,
  SERVER_TYPE_LABELS,
  TRANSPORT_OPTIONS_BASE,
  TRANSPORT_OPTIONS_WITH_STDIO,
  McpServerType,
  NewMcpServerFormInput,
  NewMcpServerFormValues,
} from '../schemas/mcpFormSchema';

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const DropzoneWithBanner: FC<{ onDrop: (files: File[]) => void; error?: string }> = ({ onDrop, error }) => (
  <>
    <Dropzone
      onDrop={onDrop}
      multiple={false}
      title={
        <span>
          Drag & drop or{' '}
          <Typography color="accent" as="span">
            select file
          </Typography>{' '}
          to upload
        </span>
      }
      dropTitle="Drop your file here"
      description="Upload to validate your agent package • Only ZIP files • Max size: 100MB"
      error={error}
    />
    <Banner
      message="Why do I need to upload an agent package?"
      description="The actions in this package will be deployed as tools in this new MCP server, ready for your agent to use."
      icon={IconLightBulb}
      variant="alert"
    />
  </>
);

type HostedMcpServerContentProps = {
  hostedUpload: UseHostedMcpUploadResult;
  onDrop: (files: File[]) => void;
};

const HostedMcpServerContent: FC<HostedMcpServerContentProps> = ({ hostedUpload, onDrop }) => {
  const { inspectionData, isPending, error } = hostedUpload;
  const actionPackages = inspectionData?.action_packages ?? [];
  const hasData = actionPackages.length > 0;

  const renderContent = (): React.ReactNode => {
    if (isPending) {
      return <Progress />;
    }

    if (hasData) {
      return (
        <Box display="grid" gap="$16">
          {actionPackages.map((actionPackage) => (
            <ActionPackageItem key={actionPackage.name} actionPackage={actionPackage} />
          ))}
        </Box>
      );
    }

    if (error) {
      return <DropzoneWithBanner onDrop={onDrop} error={error.message} />;
    }

    return <DropzoneWithBanner onDrop={onDrop} />;
  };

  const sectionTitle = hasData ? 'Action Packages' : 'Agent Package';

  return (
    <Box display="flex" flexDirection="column" gap="$16">
      <Box display="flex" flexDirection="column" gap="$12">
        <Typography fontWeight="medium">{sectionTitle}</Typography>
        {renderContent()}
      </Box>
    </Box>
  );
};

type NewMcpServerDialogProps = {
  open: boolean;
  onClose: (serverId?: string) => void;
  serverTypes: McpServerType[];
  showStdioTransport?: boolean;
};

const DEFAULT_MCP_TYPE = 'generic_mcp' as const;

const NewMcpServerDialogContent: FC<Omit<NewMcpServerDialogProps, 'open'>> = ({
  onClose,
  serverTypes,
  showStdioTransport,
}) => {
  const createMutation = useCreateMcpServerMutation({});
  const createHostedMutation = useCreateHostedMcpServerMutation({});
  const validateMutation = useValidateMcpServerCapabilitiesMutation({});

  const hostedUpload = useHostedMcpUpload();

  const typeSelectItems = serverTypes.map((type) => ({
    value: type,
    label: SERVER_TYPE_LABELS[type] || type,
  }));
  const showTypeSelector = serverTypes.length > 1;
  const defaultType = serverTypes[0] || DEFAULT_MCP_TYPE;
  const supportsHosted = serverTypes.includes('hosted');

  const form = useForm<NewMcpServerFormInput, unknown, NewMcpServerFormValues>({
    resolver: zodResolver(newMcpServerFormSchema),
    defaultValues: {
      name: '',
      type: defaultType,
      transport: 'auto',
      url: '',
      headersKV: [],
      agentPackageFile: undefined,
      agentPackageSecrets: {},
      authentication_type: 'none',
      client_credentials: {
        endpoint: '',
        client_id: '',
        client_secret: '',
        scope: '',
      },
    },
    mode: 'onChange',
  });

  const headersArray = useFieldArray({ control: form.control, name: 'headersKV' as const });
  const typeValue = form.watch('type');
  const transportValue = form.watch('transport');

  const transportOptions = showStdioTransport ? TRANSPORT_OPTIONS_WITH_STDIO : TRANSPORT_OPTIONS_BASE;

  const handleHostedDrop = useCallback(
    async (files: File[]) => {
      try {
        const result = await hostedUpload.handleDrop(files);
        if (result) {
          form.setValue('agentPackageFile', result.file, { shouldValidate: true });
          if (!form.getValues('name')) {
            form.setValue('name', `MCP server for ${result.data.name ?? ''}`);
          }
        }
      } catch (error) {
        form.setError('root', {
          type: 'manual',
          message: error instanceof Error ? error.message : 'Failed to upload file',
        });
      }
    },
    [form, hostedUpload],
  );

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.stopPropagation();
    form.handleSubmit(async (values: NewMcpServerFormValues) => {
      validateMutation.reset();

      const payload = buildCreateMcpServerPayload(values);

      if (!(values.type === 'hosted' && values.agentPackageFile)) {
        await validateMutation.mutateAsync(
          { mcpServer: payload },
          {
            onError: () => {
              // Error is available via validateMutation.error
            },
          },
        );
      }

      if (values.type === 'hosted' && values.agentPackageFile) {
        createHostedMutation.mutate(
          {
            name: payload.name,
            file: values.agentPackageFile,
            headers: payload.headers,
            mcpServerMetadata: hostedUpload.inspectionData ? { ...hostedUpload.inspectionData } : undefined,
          },
          {
            onSuccess: (result) => {
              onClose(result.mcp_server_id);
            },
            onError: (err) => {
              form.setError('root', {
                type: 'manual',
                message: err.message,
              });
            },
          },
        );
        return;
      }

      createMutation.mutate(
        { body: payload },
        {
          onSuccess: (result) => {
            onClose(result.mcp_server_id);
          },
          onError: (err) => {
            form.setError('root', {
              type: 'manual',
              message: err.message,
            });
          },
        },
      );
    })(event);
  };

  const isPending =
    createMutation.isPending || createHostedMutation.isPending || hostedUpload.isPending || validateMutation.isPending;

  const getButtonText = () => {
    if (validateMutation.isPending) return 'Validating...';
    if (createMutation.isPending || createHostedMutation.isPending) return 'Creating...';
    return 'Add';
  };

  const isHostedWithoutFile = typeValue === 'hosted' && !hostedUpload.file;
  const errorMessage = validateMutation.error?.message ?? form.formState.errors.root?.message ?? null;

  return (
    <Form onSubmit={onSubmit} busy={isPending}>
      <FormProvider {...form}>
        <Dialog.Header>
          <Dialog.Header.Title title="Add MCP Server" />
        </Dialog.Header>
        <Dialog.Content>
          <Form.Fieldset>
            <Box display="flex" flexDirection="column" gap="$24">
              <Box display="flex" flexDirection="column" gap="$16">
                <Input
                  label="Name"
                  {...form.register('name')}
                  error={form.formState.errors.name?.message}
                  placeholder="My MCP Server"
                  description="A unique name for this MCP server"
                  autoFocus
                />

                {showTypeSelector && (
                  <Controller
                    control={form.control}
                    name="type"
                    render={({ field }) => (
                      <Select
                        label="Server Type"
                        items={[...typeSelectItems]}
                        description="Select the type of MCP server"
                        {...field}
                      />
                    )}
                  />
                )}
              </Box>

              {supportsHosted && typeValue === 'hosted' && (
                <HostedMcpServerContent hostedUpload={hostedUpload} onDrop={handleHostedDrop} />
              )}

              {typeValue !== 'hosted' && (
                <>
                  {transportValue === 'stdio' ? (
                    <Input
                      label="Command"
                      {...form.register('url')}
                      error={form.formState.errors.url?.message}
                      placeholder="/usr/local/bin/mcp-server"
                      description="The command to execute"
                    />
                  ) : (
                    <Input
                      label="URL"
                      {...form.register('url')}
                      error={form.formState.errors.url?.message}
                      placeholder="https://example.com/mcp"
                      description="The MCP server endpoint URL"
                    />
                  )}

                  <Controller
                    control={form.control}
                    name="transport"
                    render={({ field }) => <Select label="Transport" items={[...transportOptions]} {...field} />}
                  />

                  {transportValue !== 'stdio' && <MCPServerAuthFields />}

                  {transportValue !== 'stdio' && (
                    <Box display="flex" flexDirection="column" gap="$8">
                      <Typography fontWeight="medium">Headers (optional)</Typography>
                      <Typography color="content.subtle" fontSize="$14">
                        Additional headers to include in requests to the MCP server
                      </Typography>
                      <Box display="grid" gap="$8" mt="$8">
                        {headersArray.fields.map((f, idx) => (
                          <Box key={f.id} display="grid" gridTemplateColumns="1fr 120px 1fr auto" gap="$8">
                            <Input
                              label="Key"
                              placeholder="Header name"
                              {...form.register(`headersKV.${idx}.key` as const)}
                            />
                            <Controller
                              control={form.control}
                              name={`headersKV.${idx}.type` as const}
                              render={({ field }) => (
                                <Select label="Type" items={[...headerTypeSelectItems]} {...field} />
                              )}
                            />
                            <Input
                              label="Value"
                              placeholder="Header value"
                              type={
                                (form.getValues(`headersKV.${idx}.type` as const) || 'string') === 'secret'
                                  ? 'password'
                                  : 'text'
                              }
                              {...form.register(`headersKV.${idx}.value` as const)}
                            />
                            <Box display="flex" alignItems="flex-end" pb="$4">
                              <Button
                                variant="ghost"
                                size="small"
                                icon={IconTrash}
                                aria-label="Remove header"
                                type="button"
                                onClick={() => headersArray.remove(idx)}
                              />
                            </Box>
                          </Box>
                        ))}
                        <Button
                          variant="outline"
                          icon={IconPlus}
                          type="button"
                          onClick={() => headersArray.append({ key: '', value: '', type: 'string' })}
                        >
                          Add Header
                        </Button>
                      </Box>
                    </Box>
                  )}
                </>
              )}

              {errorMessage && (
                <Box p="$16" borderRadius="$8" borderColor="red50">
                  <Typography color="content.error">{errorMessage}</Typography>
                </Box>
              )}
            </Box>
          </Form.Fieldset>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="outline" type="button" round onClick={() => onClose()}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" round loading={isPending} disabled={isHostedWithoutFile}>
            {getButtonText()}
          </Button>
        </Dialog.Actions>
      </FormProvider>
    </Form>
  );
};

export const NewMcpServerDialog: FC<NewMcpServerDialogProps> = ({ open, onClose, ...contentProps }) => {
  return (
    <Dialog open={open} size="x-large" onClose={onClose}>
      <NewMcpServerDialogContent onClose={onClose} {...contentProps} />
    </Dialog>
  );
};

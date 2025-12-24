import { FC } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select, Typography } from '@sema4ai/components';
import { IconLoading, IconPlus, IconTrash } from '@sema4ai/icons';
import { Controller, useFieldArray, useForm, FormProvider } from 'react-hook-form';

import { MCPServerAuthFields } from '../MCPServerAuth';
import { ActionPackageItem } from '../ActionPackage';
import { ServerResponse } from '../../../queries/shared';
import {
  editMcpServerFormSchema,
  headerTypeSelectItems,
  apiHeadersToFormEntries,
  buildUpdateMcpServerPayload,
  buildValidationPayload,
  SERVER_TYPE_LABELS,
  TRANSPORT_OPTIONS_BASE,
  TRANSPORT_OPTIONS_WITH_STDIO,
  type McpServerType,
  type EditMcpServerFormInput,
  type EditMcpServerFormValues,
} from '../schemas/mcpFormSchema';
import { apiPayloadToClientCredentials } from '../schemas/mcpAuthSchema';
import {
  useMcpServerQuery,
  useUpdateMcpServerMutation,
  useValidateMcpServerCapabilitiesMutation,
} from '../../../queries/mcpServers';

type McpServer = ServerResponse<'get', '/api/v2/mcp-servers/{mcp_server_id}'>;

type EditMcpServerFormContentProps = {
  onClose: () => void;
  server: McpServer;
  onSuccess?: () => void;
  serverTypes: McpServerType[];
  showStdioTransport: boolean;
};

/**
 * Form content component - unmounts when dialog closes, automatically resetting all state
 */
const EditMcpServerFormContent: FC<EditMcpServerFormContentProps> = ({
  onClose,
  server,
  onSuccess,
  serverTypes,
  showStdioTransport,
}) => {
  const updateMutation = useUpdateMcpServerMutation({});
  const validateMutation = useValidateMcpServerCapabilitiesMutation({});

  const isHosted = server.is_hosted === true;
  const hostedMetadata = server.mcp_server_metadata;
  const actionPackages = hostedMetadata?.action_packages ?? [];
  const isHostedWithMetadata = isHosted && actionPackages.length > 0;
  const transportOptions = showStdioTransport ? TRANSPORT_OPTIONS_WITH_STDIO : TRANSPORT_OPTIONS_BASE;

  const { entries: allEntries, secrets } = apiHeadersToFormEntries(server.headers);

  const defaultHeadersKV = isHostedWithMetadata ? allEntries.filter((e) => e.type !== 'secret') : allEntries;
  const defaultAgentPackageSecrets = isHostedWithMetadata ? secrets : {};

  const initialType = isHosted ? 'hosted' : server.type;

  const existingCredentials =
    server.authentication_type === 'oauth2-client-credentials' && server.authentication_metadata
      ? apiPayloadToClientCredentials(server.authentication_metadata)
      : undefined;

  const initialClientCredentials = existingCredentials
    ? {
        endpoint: existingCredentials.endpoint,
        client_id: existingCredentials.client_id,
        client_secret: existingCredentials.client_secret,
        scope: existingCredentials.scope,
      }
    : { endpoint: '', client_id: '', client_secret: '', scope: '' };

  const form = useForm<EditMcpServerFormInput, unknown, EditMcpServerFormValues>({
    resolver: zodResolver(editMcpServerFormSchema),
    defaultValues: {
      name: server.name,
      type: initialType,
      transport: server.transport,
      url: server.url ?? undefined,
      headersKV: defaultHeadersKV,
      command: server.command ?? undefined,
      argsText: server.args?.join(' ') ?? undefined,
      cwd: server.cwd ?? undefined,
      agentPackageSecrets: defaultAgentPackageSecrets,
      authentication_type: server.authentication_type,
      client_credentials: initialClientCredentials,
    },
    mode: 'onChange',
  });

  const transportValue = form.watch('transport');
  const headersArray = useFieldArray({ control: form.control, name: 'headersKV' as const });

  const onSubmit = form.handleSubmit(async (values: EditMcpServerFormValues) => {
    validateMutation.reset();

    const originalFields = {
      force_serial_tool_calls: server.force_serial_tool_calls,
      env: server.env,
    };
    const payloadOptions = { isHostedWithMetadata };

    const body = buildUpdateMcpServerPayload(values, originalFields, payloadOptions);
    const validationPayload = buildValidationPayload(values, originalFields, payloadOptions);

    await validateMutation.mutateAsync(
      { mcpServer: validationPayload },
      {
        onError: () => {
          // Error is available via validateMutation.error
        },
      },
    );

    updateMutation.mutate(
      { mcpServerId: server.mcp_server_id, body },
      {
        onSuccess: () => {
          onSuccess?.();
          onClose();
        },
        onError: (err) => {
          form.setError('root', {
            type: 'manual',
            message: err.message,
          });
        },
      },
    );
  });

  const effectiveServerTypes =
    isHosted && !serverTypes.includes('hosted') ? [...serverTypes, 'hosted' as const] : serverTypes;
  const typeSelectItems = effectiveServerTypes.map((type) => ({
    value: type,
    label: SERVER_TYPE_LABELS[type] || type,
  }));
  const showTypeSelector = effectiveServerTypes.length > 1;

  const isPending = updateMutation.isPending || validateMutation.isPending;

  const getButtonText = () => {
    if (validateMutation.isPending) return 'Validating...';
    if (updateMutation.isPending) return 'Saving...';
    return 'Save';
  };

  const errorMessage = validateMutation.error?.message ?? form.formState.errors.root?.message ?? null;

  return (
    <Form onSubmit={onSubmit} busy={isPending}>
      <FormProvider {...form}>
        <Dialog.Header>
          <Dialog.Header.Title title="Edit MCP Server" />
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

              {transportValue === 'stdio' ? (
                <>
                  <Input
                    label="Command"
                    placeholder="/usr/local/bin/mcp-server"
                    description="The command to execute"
                    {...form.register('command')}
                    error={form.formState.errors.command?.message}
                  />
                  <Input
                    label="Arguments"
                    placeholder="--flag value"
                    description="Space-separated arguments"
                    {...form.register('argsText')}
                    error={form.formState.errors.argsText?.message}
                  />
                  <Input
                    label="Working Directory"
                    placeholder="/path/to/dir"
                    description="Optional working directory"
                    {...form.register('cwd')}
                    error={form.formState.errors.cwd?.message}
                  />
                </>
              ) : (
                <Input
                  label="URL"
                  placeholder="https://example.com/mcp"
                  description="The MCP server endpoint URL"
                  {...form.register('url')}
                  error={form.formState.errors.url?.message}
                />
              )}

              <Controller
                control={form.control}
                name="transport"
                render={({ field }) => <Select label="Transport" items={[...transportOptions]} {...field} />}
              />

              {/* Authentication - only for URL-based transports */}
              {transportValue !== 'stdio' && <MCPServerAuthFields />}

              {isHostedWithMetadata && actionPackages.length > 0 && (
                <Box display="flex" flexDirection="column" gap="$12">
                  <Typography fontWeight="medium">Action Packages</Typography>
                  <Box display="grid" gap="$16">
                    {actionPackages.map((actionPackage) => (
                      <ActionPackageItem key={actionPackage.name} actionPackage={actionPackage} />
                    ))}
                  </Box>
                </Box>
              )}

              {transportValue !== 'stdio' && (
                <Box display="flex" flexDirection="column" gap="$8">
                  <Typography fontWeight="medium">
                    {isHostedWithMetadata ? 'Additional Headers (optional)' : 'Headers (optional)'}
                  </Typography>
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
                          render={({ field }) => <Select label="Type" items={[...headerTypeSelectItems]} {...field} />}
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

              {errorMessage && (
                <Box p="$16" borderRadius="$8" borderColor="red50">
                  <Typography color="content.error">{errorMessage}</Typography>
                </Box>
              )}
            </Box>
          </Form.Fieldset>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="outline" type="button" round onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" round loading={updateMutation.isPending}>
            {getButtonText()}
          </Button>
        </Dialog.Actions>
      </FormProvider>
    </Form>
  );
};

export type EditMcpServerDialogProps = {
  open: boolean;
  onClose: () => void;
  mcpServerId: string;
  onSuccess?: () => void;
  serverTypes: McpServerType[];
  showStdioTransport: boolean;
};

export const EditMcpServerDialog: FC<EditMcpServerDialogProps> = ({
  open,
  onClose,
  mcpServerId,
  onSuccess,
  serverTypes,
  showStdioTransport,
}) => {
  const { data: server, isLoading, error } = useMcpServerQuery({ mcpServerId });

  if (isLoading) {
    return (
      <Dialog open={open} size="x-large" onClose={onClose}>
        <Dialog.Header>
          <Dialog.Header.Title title="Edit MCP Server" />
        </Dialog.Header>
        <Dialog.Content>
          <Box display="flex" justifyContent="center" alignItems="center" p="$48">
            <IconLoading />
          </Box>
        </Dialog.Content>
      </Dialog>
    );
  }

  if (error || !server) {
    return (
      <Dialog open={open} size="x-large" onClose={onClose}>
        <Dialog.Header>
          <Dialog.Header.Title title="Edit MCP Server" />
        </Dialog.Header>
        <Dialog.Content>
          <Box p="$16" borderRadius="$8" borderColor="red50">
            <Typography color="content.error">{error?.message ?? 'Failed to load MCP server'}</Typography>
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="outline" type="button" round onClick={onClose}>
            Close
          </Button>
        </Dialog.Actions>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} size="x-large" onClose={onClose}>
      <EditMcpServerFormContent
        onClose={onClose}
        server={server}
        onSuccess={onSuccess}
        serverTypes={serverTypes}
        showStdioTransport={showStdioTransport}
      />
    </Dialog>
  );
};

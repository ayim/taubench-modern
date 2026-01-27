import { FC } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select, Typography } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { Controller, useFieldArray, useForm, FormProvider } from 'react-hook-form';

import { MCPServerAuthFields } from '../MCPServerAuth';
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
import {
  useCreateMcpServerMutation,
  useValidateMcpServerCapabilitiesMutation,
} from '../../../queries/mcpServers';

type NewMcpServerDialogProps = {
  open: boolean;
  onClose: (serverId?: string) => void;
  serverTypes: McpServerType[];
  showStdioTransport: boolean;
};

const DEFAULT_MCP_TYPE = 'generic_mcp' as const;

const NewMcpServerDialogContent: FC<Omit<NewMcpServerDialogProps, 'open'>> = ({
  onClose,
  serverTypes,
  showStdioTransport,
}) => {
  const createMutation = useCreateMcpServerMutation({});
  const validateMutation = useValidateMcpServerCapabilitiesMutation({});

  const typeSelectItems = serverTypes.map((type) => ({
    value: type,
    label: SERVER_TYPE_LABELS[type] || type,
  }));
  const showTypeSelector = serverTypes.length > 1;
  const defaultType = serverTypes[0] || DEFAULT_MCP_TYPE;

  const form = useForm<NewMcpServerFormInput, unknown, NewMcpServerFormValues>({
    resolver: zodResolver(newMcpServerFormSchema),
    defaultValues: {
      name: '',
      type: defaultType,
      transport: 'auto',
      url: '',
      headersKV: [],
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
  const transportValue = form.watch('transport');

  const transportOptions = showStdioTransport ? TRANSPORT_OPTIONS_WITH_STDIO : TRANSPORT_OPTIONS_BASE;

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.stopPropagation();
    form.handleSubmit(async (values: NewMcpServerFormValues) => {
      validateMutation.reset();

      const payload = buildCreateMcpServerPayload(values);

      await validateMutation.mutateAsync(
        { mcpServer: payload },
        {
          onError: () => {
            // Error is available via validateMutation.error
          },
        },
      );

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

  const isPending = createMutation.isPending || validateMutation.isPending;

  const getButtonText = () => {
    if (validateMutation.isPending) return 'Validating...';
    if (createMutation.isPending) return 'Creating...';
    return 'Add';
  };

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
          <Button variant="primary" type="submit" round loading={isPending}>
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

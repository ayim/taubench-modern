import { FC } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select, Typography, useSnackbar } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';
import { Controller, useFieldArray, useForm, FormProvider } from 'react-hook-form';

import { McpServer, useUpdateMcpServerMutation } from '~/queries/mcpServers';
import { InputControlled } from '~/components/InputControlled';
import { ActionPackageItem } from './ActionPackageItem';
import {
  editMcpServerFormSchema,
  EditMcpServerFormInput,
  EditMcpServerFormValues,
  apiHeadersToFormEntries,
  buildUpdateMcpServerPayload,
  mcpTypeSelectItemsWithHosted,
  mcpTransportSelectItems,
  headerTypeSelectItems,
} from '~/lib/mcpServersUtils';

export const EditMcpServerDialog: FC<{
  open: boolean;
  onClose: () => void;
  initial: McpServer;
}> = ({ open, onClose, initial }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const mutation = useUpdateMcpServerMutation();
  const { addSnackbar } = useSnackbar();

  const isHosted = initial.is_hosted === true;
  const hostedMetadata = initial.mcp_server_metadata;
  const actionPackages = hostedMetadata?.action_packages ?? [];
  const isHostedWithMetadata = isHosted && actionPackages.length > 0;

  const { entries: allEntries, secrets } = apiHeadersToFormEntries(initial.headers);

  const defaultHeadersKV = isHostedWithMetadata ? allEntries.filter((e) => e.type !== 'secret') : allEntries;
  const defaultAgentPackageSecrets = isHostedWithMetadata ? secrets : {};

  const initialType = isHosted ? 'hosted' : initial.type;

  const form = useForm<EditMcpServerFormInput, unknown, EditMcpServerFormValues>({
    resolver: zodResolver(editMcpServerFormSchema),
    defaultValues: {
      name: initial.name,
      type: initialType,
      transport: initial.transport,
      url: initial.url ?? undefined,
      headersKV: defaultHeadersKV,
      command: initial.command ?? undefined,
      argsText: initial.args?.join(' ') ?? undefined,
      cwd: initial.cwd ?? undefined,
      agentPackageSecrets: defaultAgentPackageSecrets,
    },
    mode: 'onChange',
  });

  const transportValue = form.watch('transport');
  const headersArray = useFieldArray({ control: form.control, name: 'headersKV' as const });

  const onSubmit = form.handleSubmit((values: EditMcpServerFormValues) => {
    const body = buildUpdateMcpServerPayload(
      values,
      { force_serial_tool_calls: initial.force_serial_tool_calls, env: initial.env },
      { isHostedWithMetadata },
    );

    mutation.mutate(
      { tenantId, mcpServerId: initial.mcp_server_id, body },
      {
        onSuccess: () => {
          addSnackbar({ message: 'MCP server updated', variant: 'success' });
          onClose();
        },
        onError: (e) =>
          addSnackbar({ message: e instanceof Error ? e.message : 'Failed to update MCP server', variant: 'danger' }),
      },
    );
  });

  return (
    <Dialog open={open} size={isHostedWithMetadata ? 'x-large' : 'medium'} width={900} onClose={onClose}>
      <Form onSubmit={onSubmit} gap="$12" busy={mutation.isPending} width="100%">
        <FormProvider {...form}>
          <Dialog.Header>
            <Dialog.Header.Title title="Edit MCP server" />
            <Dialog.Header.Description>Update an MCP server for your workspace.</Dialog.Header.Description>
          </Dialog.Header>
          <Dialog.Content>
            <Form.Fieldset>
              <Box display="grid" p="$4" style={{ gridTemplateColumns: '1fr', gap: '0.75rem' }}>
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
                <Controller
                  control={form.control}
                  name="transport"
                  render={({ field }) => <Select label="Transport" items={[...mcpTransportSelectItems]} {...field} />}
                />
                <Box style={{ gridColumn: '1 / -1' }}>
                  <Input
                    label="URL"
                    placeholder="URL"
                    disabled={transportValue === 'stdio'}
                    {...form.register('url')}
                    error={form.formState.errors.url?.message}
                  />
                </Box>
                {transportValue === 'stdio' && (
                  <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <Input
                      label="Command"
                      placeholder="Executable or script"
                      {...form.register('command')}
                      error={form.formState.errors.command?.message}
                    />
                    <Input
                      label="Args"
                      placeholder="e.g. --flag value"
                      {...form.register('argsText')}
                      error={form.formState.errors.argsText?.message}
                    />
                    <Input
                      label="CWD"
                      placeholder="/path/to/working/dir"
                      {...form.register('cwd')}
                      error={form.formState.errors.cwd?.message}
                    />
                  </Box>
                )}
              </Box>

              {isHostedWithMetadata && actionPackages.length > 0 && (
                <Box p="$4" display="flex" flexDirection="column" gap="$12">
                  <Typography fontWeight="medium">Action Packages</Typography>
                  <Box display="grid" gap="$16">
                    {actionPackages.map((actionPackage, idx) => (
                      <ActionPackageItem key={`${actionPackage.name}-${idx}`} actionPackage={actionPackage} />
                    ))}
                  </Box>
                </Box>
              )}

              <Box p="$4">
                <Box mb="$8">{isHostedWithMetadata ? 'Additional Headers' : 'Headers'}</Box>
                <Box display="grid" gap="$8">
                  {headersArray.fields.map((f, idx) => (
                    <Box key={f.id} display="grid" style={{ gridTemplateColumns: '1fr 160px 1fr auto', gap: '0.5rem' }}>
                      <Input label="Header key" placeholder="Key" {...form.register(`headersKV.${idx}.key` as const)} />
                      <Controller
                        control={form.control}
                        name={`headersKV.${idx}.type` as const}
                        render={({ field }) => (
                          <Select
                            label="Type"
                            items={[...headerTypeSelectItems]}
                            value={field.value}
                            onChange={field.onChange}
                            onBlur={field.onBlur}
                          />
                        )}
                      />
                      <InputControlled
                        fieldName={`headersKV.${idx}.value` as const}
                        label="Header value"
                        placeholder="Value"
                        type={(form.watch(`headersKV.${idx}.type`) || 'string') === 'secret' ? 'password' : 'text'}
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
            </Form.Fieldset>
          </Dialog.Content>
          <Dialog.Actions>
            <Button variant="primary" type="submit" round loading={mutation.isPending}>
              Save
            </Button>
            <Button variant="outline" type="button" round onClick={onClose}>
              Cancel
            </Button>
          </Dialog.Actions>
        </FormProvider>
      </Form>
    </Dialog>
  );
};

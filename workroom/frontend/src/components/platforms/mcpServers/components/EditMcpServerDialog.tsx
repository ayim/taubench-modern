import { FC, useMemo } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select, useSnackbar } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useQueryClient } from '@tanstack/react-query';
import { useParams } from '@tanstack/react-router';

import { Controller, useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';

import { buildUpdateMcpBody, headersToEntries } from '~/lib/utils';
import { McpServerResponse, useUpdateMcpServerMutation, type UpdateMcpServerBody } from '~/queries/mcpServers';
import type { MCPServerSettings } from '~/routes/tenants/$tenantId/agents/deploy/components/context';

type Props = { open: boolean; onClose: () => void; initial: McpServerResponse };

type Transport = MCPServerSettings['transport'];
type McpType = MCPServerSettings['type'];
const transportValues = ['auto', 'stdio', 'sse', 'streamable-http'] as const;
const mcpTypeValues = ['generic_mcp', 'sema4ai_action_server'] as const;

const keyValueSchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string().optional().default(''),
  type: z.enum(['string', 'secret']).optional().default('string'),
});

const formSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  type: z.enum(mcpTypeValues).default('generic_mcp'),
  transport: z.enum(transportValues).default('auto'),
  url: z.string().optional(),
  headersKV: z.array(keyValueSchema).default([]),
  command: z.string().optional(),
  argsText: z.string().optional(),
  cwd: z.string().optional(),
});

type FormInput = z.input<typeof formSchema>;
type FormValues = z.output<typeof formSchema>;

export const EditMcpServerDialog: FC<Props> = ({ open, onClose, initial }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();
  const mutation = useUpdateMcpServerMutation();
  const { addSnackbar } = useSnackbar();

  const defaultHeadersKV = useMemo(() => {
    const headers: Record<string, string | undefined> =
      (initial as unknown as { server?: { headers?: Record<string, string> } }).server?.headers ||
      (initial.headers as Record<string, string> | undefined) ||
      {};
    return headersToEntries(headers);
  }, [initial]);

  const form = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: initial.name ?? '',
      type: ((initial as unknown as { type?: McpType }).type as McpType | undefined) ?? 'generic_mcp',
      transport: (initial.transport as Transport) ?? 'auto',
      url: (initial.url as string | undefined) ?? undefined,
      headersKV: defaultHeadersKV,
      command: (initial as unknown as { command?: string | null }).command ?? undefined,
      argsText: ((initial as unknown as { args?: string[] | null }).args || [])?.join(' ') || undefined,
      cwd: (initial as unknown as { cwd?: string | null }).cwd ?? undefined,
    },
    mode: 'onChange',
  });

  const transportValue = form.watch('transport');

  const headersArray = useFieldArray({ control: form.control, name: 'headersKV' as const });

  const onSubmit = form.handleSubmit((values) => {
    const body: UpdateMcpServerBody = buildUpdateMcpBody(
      {
        name: values.name,
        type: (values.type as McpType | undefined) ?? 'generic_mcp',
        transport: values.transport,
        url: values.url,
        headerEntries: values.headersKV,
        command: values.command,
        argsText: values.argsText,
        cwd: values.cwd,
      },
      initial,
    );
    const mcpServerId = initial.mcp_server_id as string;

    mutation.mutate(
      { tenantId, mcpServerId, body },
      {
        onSuccess: async (data) => {
          queryClient.setQueryData(['mcp-server', tenantId, mcpServerId], data);
          addSnackbar({ message: 'MCP server updated', variant: 'success' });
          onClose();
        },
        onError: (e) =>
          addSnackbar({ message: e instanceof Error ? e.message : 'Failed to update MCP server', variant: 'danger' }),
      },
    );
  });

  return (
    <Dialog open={open} size="medium" width={900} onClose={onClose}>
      <Form onSubmit={onSubmit} gap="$12" busy={mutation.isPending} width="100%">
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
                render={({ field }) => (
                  <Select
                    label="Type"
                    items={mcpTypeValues.map((t) => ({
                      value: t,
                      label: t === 'generic_mcp' ? 'Generic MCP' : 'Sema4 Action Server',
                    }))}
                    value={field.value}
                    onChange={(value) => field.onChange(value as FormValues['type'])}
                  />
                )}
              />
              <Controller
                control={form.control}
                name="transport"
                render={({ field }) => (
                  <Select
                    label="Transport"
                    items={transportValues.map((t) => ({
                      value: t,
                      label: t === 'auto' ? 'Auto (Default)' : t.toUpperCase(),
                    }))}
                    value={field.value}
                    onChange={(value) => field.onChange(value as FormValues['transport'])}
                  />
                )}
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

            <Box p="$4">
              <Box mb="$8">Headers</Box>
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
                          items={[
                            { value: 'string', label: 'Plain Text' },
                            { value: 'secret', label: 'Secret' },
                          ]}
                          value={field.value as string}
                          onChange={(v) => field.onChange(v as 'string' | 'secret')}
                        />
                      )}
                    />
                    <Controller
                      control={form.control}
                      name={`headersKV.${idx}.value` as const}
                      render={({ field }) => (
                        <Input
                          label="Header value"
                          placeholder="Value"
                          type={
                            (form.getValues(`headersKV.${idx}.type` as const) || 'string') === 'secret'
                              ? 'password'
                              : 'text'
                          }
                          value={field.value as string}
                          onChange={(e) => field.onChange(e.target.value)}
                        />
                      )}
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
      </Form>
    </Dialog>
  );
};

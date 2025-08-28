import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';
import { FC, useMemo } from 'react';
import { Controller, useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';
import { McpServerResponse, useUpdateMcpServerMutation, type UpdateMcpServerBody } from '~/queries/mcpServers';
import { buildUpdateMcpBody, headersToEntries } from '~/lib/utils';
import { errorToast, successToast } from '~/utils/toasts';

type Props = { open: boolean; onClose: () => void; initial: McpServerResponse };

type Transport = UpdateMcpServerBody['transport'];
const transportValues = ['auto', 'stdio', 'sse', 'streamable-http'] as const satisfies readonly Transport[];

const keyValueSchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string().optional().default(''),
  type: z.enum(['string', 'secret']).optional().default('string'),
});

const formSchema = z
  .object({
    name: z.string().min(1, 'Name is required'),
    transport: z.enum(transportValues),
    url: z.string().optional(),
    headersKV: z.array(keyValueSchema).default([]),
    command: z.string().optional(),
    argsText: z.string().optional(),
    cwd: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.transport === 'stdio') {
      if (!values.command || !values.command.trim()) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['command'], message: 'Command is required for stdio' });
      }
    } else {
      if (!values.url || !values.url.trim()) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['url'], message: 'URL is required for this transport' });
      }
    }
  });

type FormValues = z.input<typeof formSchema>;

export const EditMcpServerDialog: FC<Props> = ({ open, onClose, initial }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const mutation = useUpdateMcpServerMutation();

  const defaultHeadersKV = useMemo(() => {
    const headers: Record<string, string | undefined> =
      (initial as unknown as { server?: { headers?: Record<string, string> } }).server?.headers ||
      (initial.headers as Record<string, string> | undefined) ||
      {};
    return headersToEntries(headers);
  }, [initial]);

  const form = useForm<FormValues, unknown, FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: initial.name ?? '',
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

  const onSubmit = form.handleSubmit((values: FormValues) => {
    const body: UpdateMcpServerBody = buildUpdateMcpBody(
      {
        name: values.name,
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
        onSuccess: () => {
          successToast('MCP server updated');
          onClose();
        },
        onError: (e) => errorToast(e instanceof Error ? e.message : 'Failed to update MCP server'),
      },
    );
  });

  return (
    <Dialog open={open} size="medium" width={900} onClose={onClose}>
      <Form onSubmit={onSubmit} gap="$12" busy={mutation.isPending}>
        <Dialog.Header>
          <Dialog.Header.Title title="Edit MCP server" />
          <Dialog.Header.Description>Update an MCP server for your workspace.</Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Form.Fieldset>
            <Box display="grid" style={{ gridTemplateColumns: '1fr', gap: '0.75rem' }}>
              <Input
                label="MCP Server Name"
                {...form.register('name')}
                error={form.formState.errors.name?.message}
                placeholder="Enter name"
                autoFocus
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

            <Box>
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

import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';
import { FC } from 'react';
import { Controller, useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';
import { useCreateMcpServerMutation, type CreateMcpServerBody } from '~/queries/mcpServers';
import { errorToast, successToast } from '~/utils/toasts';

type Props = { open: boolean; onClose: () => void };

type Transport = CreateMcpServerBody['transport'];
const transportValues = ['auto', 'stdio', 'sse', 'streamable-http'] as const satisfies readonly Transport[];

const keyValueSchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string().optional().default(''),
  type: z.enum(['string', 'secret']).optional().default('string'),
});

const formSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  transport: z.enum(transportValues),
  url: z.string().min(1, 'URL is required'),
  headersKV: z.array(keyValueSchema).default([]),
});

type FormValues = z.input<typeof formSchema>;

export const NewMcpServerDialog: FC<Props> = ({ open, onClose }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const mutation = useCreateMcpServerMutation();

  const safeParseJson = (message: unknown) => {
    if (typeof message !== 'string') return null;
    const trimmed = message.trim();
    if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null;
    try {
      return JSON.parse(trimmed) as { error?: { code?: string; message?: string } };
    } catch {
      return null;
    }
  };

  const form = useForm<FormValues, unknown, FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: '', transport: 'auto', url: '', headersKV: [] },
    mode: 'onChange',
  });

  const headersArray = useFieldArray({ control: form.control, name: 'headersKV' as const });

  const onSubmit = form.handleSubmit((values: FormValues) => {
    const headers = Object.fromEntries(
      (values.headersKV || [])
        .filter((kv: { key: string; value?: string }) => kv.key)
        .map((kv) => [kv.key, kv.value ?? '']),
    );
    // simplified: no env/args

    const body: CreateMcpServerBody = {
      name: values.name,
      transport: values.transport,
      url: values.url || undefined,
      headers: Object.keys(headers).length ? headers : undefined,
    } as CreateMcpServerBody;

    mutation.mutate(
      { tenantId, body },
      {
        onSuccess: () => {
          successToast('MCP server created');
          onClose();
        },
        onError: (e) => {
          const err = e as Error;
          const parsed = safeParseJson(err.message);
          const code = (parsed as { error?: { code?: string } } | null)?.error?.code;
          const message = (parsed as { error?: { message?: string } } | null)?.error?.message;
          errorToast(
            code || message
              ? `${code ? `[${code}] ` : ''}${message ?? ''}`
              : err.message || 'Failed to save MCP server',
          );
        },
      },
    );
  });

  return (
    <Dialog open={open} size="medium" width={900} onClose={() => onClose()}>
      <Form onSubmit={onSubmit} gap="$12" busy={mutation.isPending}>
        <Dialog.Header>
          <Dialog.Header.Title title="New MCP server" />
          <Dialog.Header.Description>Configure an MCP server for your workspace.</Dialog.Header.Description>
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
                  {...form.register('url')}
                  error={form.formState.errors.url?.message}
                />
              </Box>
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

            {/* Simplified: no environment variables or working directory */}
          </Form.Fieldset>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" type="submit" round loading={mutation.isPending}>
            Create
          </Button>
          <Button variant="outline" type="button" round onClick={() => onClose()}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};

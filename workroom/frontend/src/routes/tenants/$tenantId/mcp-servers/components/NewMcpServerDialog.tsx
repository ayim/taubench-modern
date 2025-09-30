import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select, useSnackbar } from '@sema4ai/components';
import { IconPlus, IconTrash } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';
import { FC } from 'react';
import { Controller, useFieldArray, useForm, FormProvider } from 'react-hook-form';
import { z } from 'zod';
import { buildCreateMcpBody } from '~/lib/utils';
import { useCreateMcpServerMutation, type MCPServerCreate } from '~/queries/mcpServers';
import { InputControlled } from '~/components/InputControlled';

type Props = { open: boolean; onClose: () => void };

const keyValueSchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string().optional().default(''),
  type: z.enum(['string', 'secret']).optional().default('string'),
});

const formSchema = z
  .object({
    name: z.string().min(1, 'Name is required'),
    type: z.enum(['generic_mcp', 'sema4ai_action_server']).default('generic_mcp'),
    transport: z.enum(['auto', 'streamable-http', 'sse', 'stdio']),
    url: z.string().optional(),
    headersKV: z.array(keyValueSchema).default([]),
  })
  .superRefine((values, ctx) => {
    if (values.transport !== 'stdio' && (!values.url || !values.url.trim())) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['url'], message: 'URL is required for this transport' });
    }
  });

type FormInput = z.input<typeof formSchema>;
type FormValues = z.output<typeof formSchema>;

export const NewMcpServerDialog: FC<Props> = ({ open, onClose }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const mutation = useCreateMcpServerMutation();
  const form = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      type: 'generic_mcp',
      transport: 'auto',
      url: '',
      headersKV: [],
    },
    mode: 'onChange',
  });
  const { addSnackbar } = useSnackbar();

  const headersArray = useFieldArray({ control: form.control, name: 'headersKV' as const });

  const onSubmit = form.handleSubmit((values) => {
    const body: MCPServerCreate = buildCreateMcpBody({
      name: values.name,
      type: values.type,
      transport: values.transport,
      url: values.url,
      headerEntries: values.headersKV,
    });

    mutation.mutate(
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
  });

  return (
    <Dialog open={open} width={900} onClose={() => onClose()}>
      <Form onSubmit={onSubmit} gap="$12" busy={mutation.isPending} width="100%">
        <FormProvider {...form}>
          <Dialog.Header>
            <Dialog.Header.Title title="New MCP server" />
            <Dialog.Header.Description>Configure an MCP server for your workspace.</Dialog.Header.Description>
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
                      items={[
                        { value: 'generic_mcp', label: 'Generic MCP' },
                        { value: 'sema4ai_action_server', label: 'Sema4 Action Server' },
                      ]}
                      {...field}
                    />
                  )}
                />
                <Controller
                  control={form.control}
                  name="transport"
                  render={({ field }) => (
                    <Select
                      label="Transport"
                      items={[
                        { value: 'auto', label: 'Auto (Default)' },
                        { value: 'streamable-http', label: 'STREAMABLE-HTTP' },
                        { value: 'sse', label: 'SSE' },
                        { value: 'stdio', label: 'STDIO' },
                      ]}
                      {...field}
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
                            {...field}
                          />
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
        </FormProvider>
      </Form>
    </Dialog>
  );
};

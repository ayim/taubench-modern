import { FC, useMemo, useState } from 'react';
import { Button, Dialog, Form, Input, Box, Select } from '@sema4ai/components';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  AZURE_MODEL_VALUES,
  BEDROCK_MODEL_VALUES,
  OPENAI_MODEL_VALUES,
  createOrUpdateLLMFormSchema,
  type CreateOrUpdateLLMFormSchema,
} from './llmSchemas';
import type { paths } from '@sema4ai/agent-server-interface';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { errorToast } from '~/utils/toasts';
import { beautifyLabel } from '~/lib/utils';

type Props = { open: boolean; onClose: (platformId?: string) => void };

type Provider = 'openai' | 'azure' | 'bedrock';
type ModelValue =
  | (typeof OPENAI_MODEL_VALUES)[number]
  | (typeof AZURE_MODEL_VALUES)[number]
  | (typeof BEDROCK_MODEL_VALUES)[number];

type FormValues = CreateOrUpdateLLMFormSchema;

type CreatePlatformBody = paths['/api/v2/platforms/']['post']['requestBody']['content']['application/json'];

export const NewLLMDialog: FC<Props> = ({ open, onClose }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const [selectedProvider, setSelectedProvider] = useState<Provider>('openai');
  const form = useForm<FormValues>({
    resolver: zodResolver(createOrUpdateLLMFormSchema),
    defaultValues: { name: '', model: OPENAI_MODEL_VALUES[0], provider: 'openai' },
    mode: 'onChange',
  });

  const mutation = useMutation({
    mutationFn: async (payload: CreatePlatformBody) =>
      await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/platforms/', {
        body: payload,
        errorMsg: 'Failed to create LLM',
      }),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
      onClose(data?.platform_id);
    },
    onError: (e) => {
      errorToast(e instanceof Error ? e.message : 'Failed to create LLM');
    },
  });

  const modelItems = useMemo(() => {
    const makeItems = (values: readonly string[]) =>
      values.map((v) => {
        const [prov] = v.split(':');
        return { optgroup: prov.toUpperCase(), value: v as ModelValue, label: beautifyLabel(v) };
      });

    return [...makeItems(OPENAI_MODEL_VALUES), ...makeItems(AZURE_MODEL_VALUES), ...makeItems(BEDROCK_MODEL_VALUES)];
  }, []);

  const onSubmit = form.handleSubmit(async (values) => {
    const [provider, modelId] = String(values.model).split(':');
    const credentials: Record<string, unknown> = {};
    if (provider === 'openai' && values.apiKey) {
      credentials.openai_api_key = values.apiKey;
    }
    if (provider === 'azure') {
      if (values.apiKey) credentials.azure_api_key = values.apiKey;
      if (values.azure_endpoint_url) credentials.azure_endpoint_url = values.azure_endpoint_url;
      if (values.azure_api_version) credentials.azure_api_version = values.azure_api_version;
      if (values.azure_deployment_name) credentials.azure_deployment_name = values.azure_deployment_name;
    }
    if (provider === 'bedrock') {
      if (values.aws_access_key_id) credentials.aws_access_key_id = values.aws_access_key_id;
      if (values.aws_secret_access_key) credentials.aws_secret_access_key = values.aws_secret_access_key;
      if (values.region_name) credentials.region_name = values.region_name;
    }

    const payload: CreatePlatformBody = {
      name: values.name,
      kind: provider,
      models: { [provider]: [modelId] },
      credentials: Object.keys(credentials).length ? (credentials as Record<string, unknown>) : undefined,
    };
    await mutation.mutateAsync(payload);
  });

  return (
    <Dialog
      open={open}
      size="medium"
      width={600}
      onClose={() => {
        onClose();
      }}
    >
      <Form onSubmit={onSubmit}>
        <Dialog.Header>
          <Dialog.Header.Title title="New Large Language Model (LLM)" />
          <Dialog.Header.Description>
            Agents need LLMs to function, and you can configure an agent to use any configured LLM during deployment.
          </Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Form.Fieldset>
            <Input
              label="Name"
              {...form.register('name')}
              error={form.formState.errors.name?.message}
              placeholder="Type a name"
              autoFocus
            />
            <Controller
              name="model"
              control={form.control}
              render={({ field }) => (
                <Select
                  label="Model"
                  items={modelItems}
                  value={field.value as string}
                  onChange={(value) => {
                    field.onChange(value as ModelValue);
                    const [prov] = String(value).split(':');
                    setSelectedProvider(prov as Provider);
                    form.setValue('provider', prov as Provider);
                  }}
                />
              )}
            />

            {selectedProvider === 'openai' && (
              <Input
                label="OpenAI API Key"
                type="password"
                placeholder="Enter API key"
                {...form.register('apiKey')}
                error={form.formState.errors.apiKey?.message}
              />
            )}

            {selectedProvider === 'azure' && (
              <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <Input
                  label="Azure Endpoint URL"
                  placeholder="https://...azure.com/"
                  {...form.register('azure_endpoint_url')}
                  error={form.formState.errors.azure_endpoint_url?.message}
                />
                <Input
                  label="Azure API Version"
                  placeholder="2024-02-01"
                  {...form.register('azure_api_version')}
                  error={form.formState.errors.azure_api_version?.message}
                />
                <Input
                  label="Azure Deployment Name"
                  placeholder="gpt-4-1"
                  {...form.register('azure_deployment_name')}
                  error={form.formState.errors.azure_deployment_name?.message}
                />
                <Input
                  label="Azure API Key"
                  type="password"
                  {...form.register('apiKey')}
                  error={form.formState.errors.apiKey?.message}
                />
              </Box>
            )}

            {selectedProvider === 'bedrock' && (
              <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <Input
                  label="AWS Access Key ID"
                  {...form.register('aws_access_key_id')}
                  error={form.formState.errors.aws_access_key_id?.message}
                />
                <Input
                  label="AWS Secret Access Key"
                  type="password"
                  {...form.register('aws_secret_access_key')}
                  error={form.formState.errors.aws_secret_access_key?.message}
                />
                <Input
                  label="Region"
                  placeholder="us-east-1"
                  {...form.register('region_name')}
                  error={form.formState.errors.region_name?.message}
                />
              </Box>
            )}
          </Form.Fieldset>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" type="submit" round disabled={mutation.isPending}>
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

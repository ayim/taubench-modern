import { FC, useMemo } from 'react';
import { Box, Button, Dialog, Form, Input, Select } from '@sema4ai/components';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { errorToast, successToast } from '~/utils/toasts';
import {
  AZURE_MODEL_VALUES,
  BEDROCK_MODEL_VALUES,
  OPENAI_MODEL_VALUES,
  editLLMFormSchema,
  type EditLLMFormSchema,
} from '~/components/platforms/llms/components/llmSchemas';
import type { paths } from '@sema4ai/agent-server-interface';

type GetPlatformResponse =
  paths['/api/v2/platforms/{platform_id}']['get']['responses']['200']['content']['application/json'];
type UpdatePlatformBody = paths['/api/v2/platforms/{platform_id}']['put']['requestBody']['content']['application/json'];

type Props = {
  platformId: string;
  open: boolean;
  onClose: () => void;
  onUpdated?: (platform: GetPlatformResponse) => void;
  initial?: {
    name: string;
    provider: Provider;
    model?: string;
  };
  existingKeys?: { openai?: boolean; azure?: boolean; bedrock?: boolean };
};

type Provider = 'openai' | 'azure' | 'bedrock';
type ModelValue =
  | (typeof OPENAI_MODEL_VALUES)[number]
  | (typeof AZURE_MODEL_VALUES)[number]
  | (typeof BEDROCK_MODEL_VALUES)[number];

type FormValues = EditLLMFormSchema;

export const EditPlatformDialog: FC<Props> = ({ platformId, open, onClose, onUpdated, initial }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();
  const kind: Provider = initial?.provider ?? 'openai';
  const defaultModel: ModelValue = (() => {
    const modelPrefix = kind + ':';
    if (initial?.model && initial.model.startsWith(modelPrefix)) return initial.model as ModelValue;
    if (kind === 'azure') return AZURE_MODEL_VALUES[0];
    if (kind === 'bedrock') return BEDROCK_MODEL_VALUES[0];
    return OPENAI_MODEL_VALUES[0];
  })();
  const form = useForm<FormValues>({
    resolver: zodResolver(editLLMFormSchema),
    defaultValues: {
      name: initial?.name ?? '',
      provider: kind,
      model: defaultModel,
      apiKey: undefined,
      azure_endpoint_url: undefined,
      azure_api_version: undefined,
      azure_deployment_name: undefined,
      aws_access_key_id: undefined,
      aws_secret_access_key: undefined,
      region_name: undefined,
    },
    mode: 'onChange',
  });

  const isAzure = kind === 'azure';
  const isBedrock = kind === 'bedrock';

  const mutation = useMutation({
    mutationFn: async (payload: UpdatePlatformBody) =>
      (await agentAPIClient.agentFetch(tenantId, 'put', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
        body: payload as never,
        errorMsg: 'Failed to update platform',
      })) as GetPlatformResponse,
    onSuccess: async (updated) => {
      successToast('Platform updated');
      onUpdated?.(updated);
      await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
      await queryClient.invalidateQueries({ queryKey: ['platform', tenantId, platformId] });
      onClose();
    },
    onError: (e) => {
      errorToast(e instanceof Error ? e.message : 'Failed to update platform');
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const credentials: Record<string, unknown> = {};
    const [provider, modelId] = String(values.model).split(':');

    if (provider === 'openai') {
      if (values.apiKey) credentials.openai_api_key = values.apiKey;
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

    const payload = {
      id: platformId,
      name: values.name,
      kind: provider,
      models: { [provider]: [modelId] },
      credentials: Object.keys(credentials).length ? credentials : undefined,
    } as unknown as UpdatePlatformBody;

    await mutation.mutateAsync(payload);
  });

  const modelItems = useMemo(() => {
    const forProvider = (values: readonly string[]) =>
      values
        .filter((v) => v.startsWith(kind + ':'))
        .map((v) => ({ value: v as ModelValue, label: v.split(':')[1] || v }));
    if (kind === 'azure') return forProvider(AZURE_MODEL_VALUES);
    if (kind === 'bedrock') return forProvider(BEDROCK_MODEL_VALUES);
    return forProvider(OPENAI_MODEL_VALUES);
  }, [kind]);

  return (
    <Dialog open={open} size="medium" onClose={onClose}>
      <Form onSubmit={onSubmit}>
        <Dialog.Header>
          <Dialog.Header.Title title="Edit Model Platform" />
        </Dialog.Header>
        <Dialog.Content>
          <Box display="flex" flexDirection="column" gap="$16">
            <Input label="Name" {...form.register('name')} error={form.formState.errors.name?.message} />
            <Controller
              name="model"
              control={form.control}
              render={({ field }) => (
                <Select
                  label="Model"
                  items={modelItems}
                  value={field.value as string}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  ref={field.ref}
                />
              )}
            />

            {kind === 'openai' && (
              <Input
                label="OpenAI API Key"
                type="password"
                {...form.register('apiKey')}
                error={form.formState.errors.apiKey?.message}
              />
            )}

            {isAzure && (
              <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <Input label="Azure Endpoint URL" {...form.register('azure_endpoint_url')} />
                <Input label="Azure API Version" {...form.register('azure_api_version')} />
                <Input label="Azure Deployment Name" {...form.register('azure_deployment_name')} />
                <Input label="Azure API Key" type="password" {...form.register('apiKey')} />
              </Box>
            )}

            {isBedrock && (
              <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <Input label="AWS Access Key ID" {...form.register('aws_access_key_id')} />
                <Input label="AWS Secret Access Key" type="password" {...form.register('aws_secret_access_key')} />
                <Input label="Region" {...form.register('region_name')} />
              </Box>
            )}
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="outline" round type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" round type="submit" disabled={mutation.isPending}>
            Save
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};

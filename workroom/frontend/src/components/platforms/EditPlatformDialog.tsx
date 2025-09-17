import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, Select, useSnackbar } from '@sema4ai/components';
import { FC, useMemo } from 'react';
import { Controller, FormProvider, useForm } from 'react-hook-form';
import { InputControlled } from '~/components/InputControlled';
import {
  AZURE_MODEL_VALUES,
  BEDROCK_MODEL_VALUES,
  OPENAI_MODEL_VALUES,
  editLLMFormSchema,
  type EditLLMFormSchema,
  type Provider,
} from '~/components/platforms/llms/components/llmSchemas';
import { useUpdateLLMMutation, type GetPlatformResponse, type UpdatePlatformBody } from '~/queries/platforms';

type Props = {
  open: boolean;
  onClose: () => void;
  onUpdated?: (platform: GetPlatformResponse) => void;
  platform: GetPlatformResponse;
  tenantId: string;
};

type FormValues = EditLLMFormSchema;

export const EditPlatformDialog: FC<Props> = ({ platform, open, onClose, onUpdated, tenantId }) => {
  const { addSnackbar } = useSnackbar();

  const providerId = String(platform.kind || 'openai').toLowerCase();
  const isValidProvider = (p: string): p is Provider => ['openai', 'azure', 'bedrock'].includes(p);
  const kind: Provider = isValidProvider(providerId) ? providerId : 'openai';
  const firstModel = (platform.models?.[providerId] || [])[0];

  const modelString = firstModel ? `${kind}:${firstModel}` : undefined;
  const isValidModel = (m: string): m is EditLLMFormSchema['model'] => {
    const allValidModels = [...AZURE_MODEL_VALUES, ...BEDROCK_MODEL_VALUES, ...OPENAI_MODEL_VALUES];
    return allValidModels.some((validModel) => validModel === m);
  };
  const currentModel = modelString && isValidModel(modelString) ? modelString : undefined;

  // TODO: Tighten platform types and platformKind logic in another PR - improve type discrimination
  const getPlatformConfig = () => {
    const baseConfig = {
      name: platform.name,
      provider: kind,
      model:
        currentModel ||
        (kind === 'azure'
          ? AZURE_MODEL_VALUES[0]
          : kind === 'bedrock'
            ? BEDROCK_MODEL_VALUES[0]
            : OPENAI_MODEL_VALUES[0]),
      apiKey: undefined,
      aws_secret_access_key: undefined,
    };

    if (platform.kind === 'azure') {
      return {
        ...baseConfig,
        azure_endpoint_url: platform.azure_endpoint_url || undefined,
        azure_api_version: platform.azure_api_version || undefined,
        azure_deployment_name: platform.azure_deployment_name || undefined,
        aws_access_key_id: undefined,
        region_name: undefined,
      };
    }

    if (platform.kind === 'bedrock') {
      return {
        ...baseConfig,
        azure_endpoint_url: undefined,
        azure_api_version: undefined,
        azure_deployment_name: undefined,
        aws_access_key_id: platform.aws_access_key_id || undefined,
        region_name: platform.region_name || undefined,
      };
    }

    return {
      ...baseConfig,
      azure_endpoint_url: undefined,
      azure_api_version: undefined,
      azure_deployment_name: undefined,
      aws_access_key_id: undefined,
      region_name: undefined,
    };
  };

  const form = useForm<FormValues>({
    resolver: zodResolver(editLLMFormSchema),
    defaultValues: getPlatformConfig(),
    mode: 'onChange',
  });

  const isAzure = kind === 'azure';
  const isBedrock = kind === 'bedrock';

  const mutation = useUpdateLLMMutation();

  const onSubmit = form.handleSubmit((values) => {
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
      id: platform.platform_id,
      name: values.name,
      kind: provider,
      models: { [provider]: [modelId] },
      credentials: Object.keys(credentials).length ? credentials : undefined,
    } satisfies UpdatePlatformBody;

    mutation.mutate(
      { tenantId, platformId: platform.platform_id, body: payload },
      {
        onSuccess: async (updated) => {
          addSnackbar({ message: 'LLM updated', variant: 'success' });
          onUpdated?.(updated);
          onClose();
        },
        onError: (error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  });

  const modelItems = useMemo(() => {
    const forProvider = (values: readonly string[]) =>
      values
        .filter((modelValue) => modelValue.startsWith(kind + ':'))
        .map((modelValue) => ({ value: modelValue, label: modelValue.split(':')[1] || modelValue }));
    if (kind === 'azure') return forProvider(AZURE_MODEL_VALUES);
    if (kind === 'bedrock') return forProvider(BEDROCK_MODEL_VALUES);
    return forProvider(OPENAI_MODEL_VALUES);
  }, [kind]);

  return (
    <Dialog open={open} onClose={onClose} width={600}>
      <Form onSubmit={onSubmit} width="100%">
        <FormProvider {...form}>
          <Dialog.Header>
            <Dialog.Header.Title title="Edit LLM" />
          </Dialog.Header>
          <Dialog.Content>
            <Box display="flex" flexDirection="column" gap="$16" p="$4">
              <Input label="Name" {...form.register('name')} error={form.formState.errors.name?.message} />
              <Controller
                name="model"
                control={form.control}
                render={({ field }) => (
                  <Select
                    label="Model"
                    items={modelItems}
                    value={String(field.value)}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    ref={field.ref}
                  />
                )}
              />

              {kind === 'openai' && <InputControlled fieldName="apiKey" label="OpenAI API Key" type="password" />}

              {isAzure && (
                <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <Input label="Azure Endpoint URL" {...form.register('azure_endpoint_url')} />
                  <Input label="Azure API Version" {...form.register('azure_api_version')} />
                  <Input label="Azure Deployment Name" {...form.register('azure_deployment_name')} />
                  <InputControlled fieldName="apiKey" label="Azure API Key" type="password" />
                </Box>
              )}

              {isBedrock && (
                <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <Input label="AWS Access Key ID" {...form.register('aws_access_key_id')} />
                  <InputControlled fieldName="aws_secret_access_key" label="AWS Secret Access Key" type="password" />
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
        </FormProvider>
      </Form>
    </Dialog>
  );
};

import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Checkbox, Dialog, Form, Input, Select, useSnackbar } from '@sema4ai/components';
import { useRouter } from '@tanstack/react-router';
import { FC, useEffect, useMemo } from 'react';
import { Controller, FormProvider, useForm } from 'react-hook-form';
import { InputControlled } from '~/components/InputControlled';
import {
  AZURE_MODEL_VALUES,
  AZURE_FOUNDRY_MODEL_VALUES,
  BEDROCK_MODEL_VALUES,
  GROQ_MODEL_VALUES,
  GOOGLE_MODEL_VALUES,
  OPENAI_MODEL_VALUES,
  editLLMFormSchema,
  getGroqProviderForModel,
  getAzureFoundryModelFamily,
  type EditLLMFormSchema,
  type Platform,
} from '~/components/platforms/llms/components/llmSchemas';
import { VertexServiceAccountUploadField } from '~/components/platforms/llms/components/VertexServiceAccountUploadField';
import { beautifyLabel, getAllowedModelFromPlatform, normalizeAzureEndpointUrl } from '~/lib/utils';
import { type PlatformForEditing } from '~/queries/agent-interface-patches';
import { useUpdateLLMMutation, type GetPlatformResponse, type UpdatePlatformBody } from '~/queries/platforms';

type Props = {
  open: boolean;
  onClose: () => void;
  onUpdated?: (platform: GetPlatformResponse) => void;
  platform: GetPlatformResponse;
};

type GooglePlatformExtras = {
  google_cloud_project_id?: string | null;
  google_cloud_location?: string | null;
  google_use_vertex_ai?: boolean | null;
  google_vertex_service_account_json?: string | null;
};

type AzureFoundryPlatformExtras = {
  endpoint_url?: string | null;
  api_key?: { value?: string } | null;
  deployment_name?: string | null;
};

export const EditPlatformDialog: FC<Props> = ({ platform, open, onClose, onUpdated }) => {
  const { addSnackbar } = useSnackbar();
  const kind = platform.kind as Platform;
  const router = useRouter();

  const firstModel = getAllowedModelFromPlatform(platform);
  // For azure_foundry, construct the triple-segment format
  const getCurrentModel = () => {
    if (kind === 'azure_foundry') {
      return `azure_foundry:anthropic:${firstModel}`;
    }
    return firstModel ? `${kind}:${firstModel}` : `${kind}:unknown`;
  };
  const currentModel = getCurrentModel();

  const platformConfig = useMemo(() => {
    const base = { name: platform.name, platform: kind, model: currentModel, validateLLM: true };

    return {
      ...base,
      ...(platform.kind === 'azure' && {
        apiKey: platform.azure_api_key?.value,
        azure_endpoint_url: platform.azure_endpoint_url,
        azure_api_version: platform.azure_api_version,
        azure_deployment_name: platform.azure_deployment_name,
      }),
      ...(platform.kind === 'bedrock' && {
        aws_secret_access_key: platform.aws_secret_access_key,
        aws_access_key_id: platform.aws_access_key_id,
        region_name: platform.region_name,
      }),
      ...(platform.kind === 'openai' && {
        apiKey: platform.openai_api_key?.value,
      }),
      ...(platform.kind === 'groq' && {
        apiKey: platform.groq_api_key?.value,
      }),
      ...(platform.kind === 'google' && {
        google_api_key: platform.google_api_key?.value,
        google_use_vertex_ai: (platform as PlatformForEditing & GooglePlatformExtras).google_use_vertex_ai ?? false,
        google_cloud_project_id:
          (platform as PlatformForEditing & GooglePlatformExtras).google_cloud_project_id ?? undefined,
        google_cloud_location:
          (platform as PlatformForEditing & GooglePlatformExtras).google_cloud_location ?? undefined,
        google_vertex_service_account_json:
          (platform as PlatformForEditing & GooglePlatformExtras).google_vertex_service_account_json ?? undefined,
      }),
      ...(platform.kind === 'azure_foundry' && {
        azure_foundry_endpoint_url:
          (platform as PlatformForEditing & AzureFoundryPlatformExtras).endpoint_url ?? undefined,
        azure_foundry_api_key:
          (platform as PlatformForEditing & AzureFoundryPlatformExtras).api_key?.value ?? undefined,
        azure_foundry_deployment_name:
          (platform as PlatformForEditing & AzureFoundryPlatformExtras).deployment_name ?? undefined,
      }),
    };
  }, [platform, kind, currentModel]);

  const form = useForm<EditLLMFormSchema>({
    resolver: zodResolver(editLLMFormSchema),
    defaultValues: platformConfig,
    mode: 'onChange',
  });

  useEffect(() => {
    form.reset(platformConfig);
  }, [platformConfig, form]);

  const isAzure = kind === 'azure';
  const isAzureFoundry = kind === 'azure_foundry';
  const isBedrock = kind === 'bedrock';
  const isGroq = kind === 'groq';
  const isGoogle = kind === 'google';
  const googleUseVertexAI = form.watch('google_use_vertex_ai');

  const mutation = useUpdateLLMMutation();

  const onSubmit = form.handleSubmit((values) => {
    const modelValue = String(values.model);
    const parts = modelValue.split(':');

    // Handle triple-segment format for azure_foundry (azure_foundry:family:model)
    let modelId: string;
    if (parts[0] === 'azure_foundry' && parts.length === 3) {
      [, , modelId] = parts;
    } else {
      modelId = parts[1] ?? modelValue;
    }

    const credentials: Record<string, unknown> = {};
    let provider: string | null = null;

    if (kind === 'azure') {
      if (values.apiKey) credentials.azure_api_key = values.apiKey;
      if (values.azure_endpoint_url) credentials.azure_endpoint_url = values.azure_endpoint_url;
      if (values.azure_api_version) credentials.azure_api_version = values.azure_api_version;
      if (values.azure_deployment_name) credentials.azure_deployment_name = values.azure_deployment_name;
      provider = 'openai';
    } else if (kind === 'azure_foundry') {
      if (values.azure_foundry_endpoint_url)
        credentials.endpoint_url = normalizeAzureEndpointUrl(values.azure_foundry_endpoint_url);
      if (values.azure_foundry_api_key) credentials.api_key = values.azure_foundry_api_key;
      if (values.azure_foundry_deployment_name) credentials.deployment_name = values.azure_foundry_deployment_name;
      if (values.azure_foundry_api_version) credentials.azure_foundry_api_version = values.azure_foundry_api_version;
      // Provider comes from the model value for azure_foundry
      provider = getAzureFoundryModelFamily(modelValue) ?? 'anthropic';
    } else if (kind === 'bedrock') {
      if (values.aws_access_key_id) credentials.aws_access_key_id = values.aws_access_key_id;
      if (values.aws_secret_access_key) credentials.aws_secret_access_key = values.aws_secret_access_key;
      if (values.region_name) credentials.region_name = values.region_name;
      provider = 'anthropic';
    } else if (kind === 'openai') {
      if (values.apiKey) credentials.openai_api_key = values.apiKey;
      provider = 'openai';
    } else if (kind === 'groq') {
      if (values.apiKey) credentials.groq_api_key = values.apiKey;
      provider = getGroqProviderForModel(modelValue) ?? null;
    } else if (kind === 'google') {
      if (values.google_api_key) credentials.google_api_key = values.google_api_key;
      if (typeof values.google_use_vertex_ai === 'boolean')
        credentials.google_use_vertex_ai = values.google_use_vertex_ai;
      if (values.google_use_vertex_ai) {
        if (values.google_cloud_project_id) credentials.google_cloud_project_id = values.google_cloud_project_id;
        if (values.google_cloud_location) credentials.google_cloud_location = values.google_cloud_location;
        if (values.google_vertex_service_account_json)
          credentials.google_vertex_service_account_json = values.google_vertex_service_account_json;
      }
      provider = 'google';
    }

    if (!provider) {
      addSnackbar({ message: 'Unable to determine provider for selected model.', variant: 'danger' });
      return;
    }

    const payload = {
      id: platform.platform_id,
      name: values.name,
      kind,
      ...(provider ? { models: { [provider]: [modelId] } } : {}),
      credentials: Object.keys(credentials).length ? credentials : undefined,
    } satisfies UpdatePlatformBody;

    mutation.mutate(
      { platformId: platform.platform_id, validateLLM: values.validateLLM, body: payload },
      {
        onSuccess: async (updated) => {
          addSnackbar({ message: 'LLM updated', variant: 'success' });
          await router.invalidate();
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
    const forPlatform = (values: readonly string[]) =>
      values
        .filter((modelValue) => modelValue.startsWith(`${kind}:`))
        .map((modelValue) => ({ value: modelValue, label: beautifyLabel(modelValue) }));
    if (kind === 'azure') return forPlatform(AZURE_MODEL_VALUES);
    if (kind === 'azure_foundry') return forPlatform(AZURE_FOUNDRY_MODEL_VALUES);
    if (kind === 'bedrock') return forPlatform(BEDROCK_MODEL_VALUES);
    if (kind === 'openai') return forPlatform(OPENAI_MODEL_VALUES);
    if (kind === 'google') return forPlatform(GOOGLE_MODEL_VALUES);
    if (kind === 'groq') return forPlatform(GROQ_MODEL_VALUES);

    return [];
  }, [kind]);

  return (
    <Dialog open={open} onClose={onClose} width={600}>
      <Form onSubmit={onSubmit} width="100%" busy={mutation.isPending}>
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
              <Controller
                name="validateLLM"
                control={form.control}
                render={({ field }) => (
                  <Checkbox
                    checked={field.value}
                    onChange={field.onChange}
                    label="Validate LLM Configuration"
                    description="By default, a connectivity test will run using these settings before saving. Uncheck this if your LLM is behind strict network rules that prevent validation."
                  />
                )}
              />

              {kind === 'openai' && <InputControlled fieldName="apiKey" label="OpenAI API Key" type="password" />}

              {isGroq && <InputControlled fieldName="apiKey" label="Groq API Key" type="password" />}

              {isAzure && (
                <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <Input label="Azure Endpoint URL" {...form.register('azure_endpoint_url')} />
                  <Input label="Azure API Version" {...form.register('azure_api_version')} />
                  <Input label="Azure Deployment Name" {...form.register('azure_deployment_name')} />
                  <InputControlled fieldName="apiKey" label="Azure API Key" type="password" />
                </Box>
              )}

              {isAzureFoundry && (
                <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <Input
                    label="Endpoint URL"
                    placeholder="https://my-resource.services.ai.azure.com"
                    {...form.register('azure_foundry_endpoint_url')}
                    error={form.formState.errors.azure_foundry_endpoint_url?.message}
                  />
                  <InputControlled fieldName="azure_foundry_api_key" label="API Key" type="password" />
                  <Input
                    label="Deployment Name"
                    placeholder="claude-4-5-sonnet"
                    {...form.register('azure_foundry_deployment_name')}
                    error={form.formState.errors.azure_foundry_deployment_name?.message}
                  />
                  <Input
                    label="API Version (OpenAI only)"
                    placeholder="2024-12-01-preview"
                    {...form.register('azure_foundry_api_version')}
                    error={form.formState.errors.azure_foundry_api_version?.message}
                  />
                </Box>
              )}

              {isBedrock && (
                <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <Input label="AWS Access Key ID" {...form.register('aws_access_key_id')} />
                  <InputControlled fieldName="aws_secret_access_key" label="AWS Secret Access Key" type="password" />
                  <Input label="Region" {...form.register('region_name')} />
                </Box>
              )}

              {isGoogle && (
                <Box display="flex" flexDirection="column" gap="$12">
                  {!googleUseVertexAI && (
                    <InputControlled fieldName="google_api_key" label="Google API Key" type="password" />
                  )}
                  <Controller
                    name="google_use_vertex_ai"
                    control={form.control}
                    render={({ field }) => (
                      <Checkbox
                        checked={Boolean(field.value)}
                        onChange={field.onChange}
                        label="Use Google Vertex AI"
                        description="Enable if this configuration should route through Vertex AI."
                      />
                    )}
                  />
                  {googleUseVertexAI && (
                    <Box display="flex" flexDirection="column" gap="$8">
                      <Input
                        label="Google Cloud Project ID"
                        placeholder="my-gcp-project"
                        {...form.register('google_cloud_project_id')}
                        error={form.formState.errors.google_cloud_project_id?.message}
                      />
                      <Input
                        label="Google Cloud Location"
                        placeholder="us-central1"
                        {...form.register('google_cloud_location')}
                        error={form.formState.errors.google_cloud_location?.message}
                      />
                      <VertexServiceAccountUploadField />
                    </Box>
                  )}
                </Box>
              )}
            </Box>
          </Dialog.Content>
          <Dialog.Actions>
            <Button variant="primary" round type="submit" loading={mutation.isPending}>
              Save
            </Button>
            <Button variant="secondary" round type="button" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
          </Dialog.Actions>
        </FormProvider>
      </Form>
    </Dialog>
  );
};

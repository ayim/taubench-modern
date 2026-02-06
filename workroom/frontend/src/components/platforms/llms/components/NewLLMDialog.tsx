import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Checkbox, Dialog, Form, Input, Select, useSnackbar } from '@sema4ai/components';
import { FC, useMemo, useState } from 'react';
import { Controller, FormProvider, useForm } from 'react-hook-form';
import { InputControlled } from '~/components/InputControlled';
import { beautifyLabel, normalizeAzureEndpointUrl } from '~/lib/utils';
import { useCreateLLMMutation, type CreatePlatformBody } from '~/queries/platforms';
import { VertexServiceAccountUploadField } from './VertexServiceAccountUploadField';
import {
  AZURE_MODEL_VALUES,
  AZURE_FOUNDRY_MODEL_VALUES,
  BEDROCK_MODEL_VALUES,
  GROQ_MODEL_VALUES,
  OPENAI_MODEL_VALUES,
  GOOGLE_MODEL_VALUES,
  Platform,
  createOrUpdateLLMFormSchema,
  getGroqProviderForModel,
  getAzureFoundryModelFamily,
  isPlatformValue,
  parseModelValue,
  type CreateOrUpdateLLMFormSchema,
} from './llmSchemas';

type Props = { open: boolean; onClose: (platformId?: string) => void };

export const NewLLMDialog: FC<Props> = ({ open, onClose }) => {
  const { addSnackbar } = useSnackbar();
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('openai');
  const form = useForm<CreateOrUpdateLLMFormSchema>({
    resolver: zodResolver(createOrUpdateLLMFormSchema),
    defaultValues: {
      name: '',
      model: OPENAI_MODEL_VALUES[0],
      platform: 'openai',
      validateLLM: true,
      google_use_vertex_ai: false,
      google_vertex_service_account_json: undefined,
    },
    mode: 'onChange',
  });
  const googleUseVertexAI = form.watch('google_use_vertex_ai');

  const mutation = useCreateLLMMutation();

  const modelItems = useMemo(() => {
    const makeItems = (values: readonly string[], optgroupOverride?: string) =>
      values.map((modelValue) => {
        const [providerPrefix] = modelValue.split(':');
        return {
          optgroup: optgroupOverride ?? providerPrefix.toUpperCase(),
          value: modelValue,
          label: beautifyLabel(modelValue),
        };
      });

    return [
      ...makeItems(OPENAI_MODEL_VALUES),
      ...makeItems(AZURE_MODEL_VALUES),
      ...makeItems(AZURE_FOUNDRY_MODEL_VALUES, 'AZURE FOUNDRY'),
      ...makeItems(BEDROCK_MODEL_VALUES),
      ...makeItems(GROQ_MODEL_VALUES),
      ...makeItems(GOOGLE_MODEL_VALUES),
    ];
  }, []);

  const onSubmit = form.handleSubmit((values) => {
    const modelValue = String(values.model);
    const { platform, modelId, provider: parsedProvider } = parseModelValue(modelValue, selectedPlatform);
    let provider = parsedProvider;

    const credentials: Record<string, unknown> = {};

    if (platform === 'openai' && values.apiKey) {
      credentials.openai_api_key = values.apiKey;
      provider = 'openai';
    } else if (platform === 'azure') {
      if (values.apiKey) credentials.azure_api_key = values.apiKey;
      if (values.azure_endpoint_url) credentials.azure_endpoint_url = values.azure_endpoint_url;
      if (values.azure_api_version) credentials.azure_api_version = values.azure_api_version;
      if (values.azure_deployment_name) credentials.azure_deployment_name = values.azure_deployment_name;
      provider = 'openai';
    } else if (platform === 'azure_foundry') {
      if (values.azure_foundry_endpoint_url)
        credentials.endpoint_url = normalizeAzureEndpointUrl(values.azure_foundry_endpoint_url);
      if (values.azure_foundry_api_key) credentials.api_key = values.azure_foundry_api_key;
      if (values.azure_foundry_deployment_name) credentials.deployment_name = values.azure_foundry_deployment_name;
      if (values.azure_foundry_api_version) credentials.azure_foundry_api_version = values.azure_foundry_api_version;
      // Provider comes from the parsed model value for azure_foundry
      if (!provider) {
        provider = getAzureFoundryModelFamily(modelValue) ?? 'anthropic';
      }
    } else if (platform === 'google') {
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
    } else if (platform === 'bedrock') {
      if (values.aws_access_key_id) credentials.aws_access_key_id = values.aws_access_key_id;
      if (values.aws_secret_access_key) credentials.aws_secret_access_key = values.aws_secret_access_key;
      if (values.region_name) credentials.region_name = values.region_name;
      // This logic was a bit messed up: _provider_ is anthropic, not bedrock
      // bedrock is a platform
      provider = 'anthropic';
    } else if (platform === 'groq') {
      if (values.apiKey) credentials.groq_api_key = values.apiKey;
      provider = getGroqProviderForModel(modelValue) ?? null;
    }

    if (!provider) {
      addSnackbar({
        message: 'Unable to determine provider for selected model.',
        variant: 'danger',
      });
      return;
    }
    const payload: CreatePlatformBody = {
      name: values.name,
      kind: platform,
      ...(provider ? { models: { [provider]: [modelId] } } : {}),
      credentials: Object.keys(credentials).length ? credentials : undefined,
    };

    mutation.mutate(
      { validateLLM: values.validateLLM, body: payload },
      {
        onSuccess: (data) => {
          onClose(data?.platform_id);
        },
        onError: (error) => {
          addSnackbar({
            message: error.message,
            variant: 'danger',
          });
        },
      },
    );
  });

  return (
    <Dialog
      open={open}
      width={600}
      onClose={() => {
        onClose();
      }}
    >
      <Form onSubmit={onSubmit} busy={mutation.isPending}>
        <FormProvider {...form}>
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
                    value={String(field.value)}
                    onChange={(selectedModel) => {
                      field.onChange(selectedModel);
                      const modelStr = String(selectedModel);
                      const parts = modelStr.split(':');
                      // Handle triple-segment format for azure_foundry
                      if (parts[0] === 'azure_foundry') {
                        setSelectedPlatform('azure_foundry');
                        form.setValue('platform', 'azure_foundry');
                      } else if (isPlatformValue(parts[0])) {
                        setSelectedPlatform(parts[0] as Platform);
                        form.setValue('platform', parts[0] as Platform);
                      }
                    }}
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

              {selectedPlatform === 'openai' && (
                <InputControlled
                  fieldName="apiKey"
                  label="OpenAI API Key"
                  type="password"
                  placeholder="Enter API key"
                />
              )}

              {selectedPlatform === 'groq' && (
                <InputControlled fieldName="apiKey" label="Groq API Key" type="password" placeholder="Enter API key" />
              )}
              {selectedPlatform === 'google' && (
                <Box display="flex" flexDirection="column" gap="$12">
                  {!googleUseVertexAI && (
                    <InputControlled
                      fieldName="google_api_key"
                      label="Google API Key"
                      type="password"
                      placeholder="Enter API key"
                    />
                  )}
                  <Controller
                    name="google_use_vertex_ai"
                    control={form.control}
                    render={({ field }) => (
                      <Checkbox
                        checked={Boolean(field.value)}
                        onChange={field.onChange}
                        label="Use Google Vertex AI"
                        description="Enable if your Gemini deployment is configured through Vertex AI."
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

              {selectedPlatform === 'azure' && (
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
                  <InputControlled fieldName="apiKey" label="Azure API Key" type="password" />
                </Box>
              )}

              {selectedPlatform === 'azure_foundry' && (
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

              {selectedPlatform === 'bedrock' && (
                <Box display="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <Input
                    label="AWS Access Key ID"
                    {...form.register('aws_access_key_id')}
                    error={form.formState.errors.aws_access_key_id?.message}
                  />
                  <InputControlled fieldName="aws_secret_access_key" label="AWS Secret Access Key" type="password" />
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
            <Button variant="primary" type="submit" round loading={mutation.isPending}>
              Create
            </Button>
            <Button variant="secondary" type="button" round onClick={() => onClose()} disabled={mutation.isPending}>
              Cancel
            </Button>
          </Dialog.Actions>
        </FormProvider>
      </Form>
    </Dialog>
  );
};

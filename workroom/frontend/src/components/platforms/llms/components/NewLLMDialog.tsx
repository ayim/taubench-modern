import { FC, useMemo, useState } from 'react';
import { Button, Dialog, Form, Input, Box, Select, useSnackbar } from '@sema4ai/components';
import { useParams } from '@tanstack/react-router';
import { useForm, Controller, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  AZURE_MODEL_VALUES,
  BEDROCK_MODEL_VALUES,
  OPENAI_MODEL_VALUES,
  Provider,
  createOrUpdateLLMFormSchema,
  type CreateOrUpdateLLMFormSchema,
} from './llmSchemas';
import { beautifyLabel } from '~/lib/utils';
import { useCreateLLMMutation, type CreatePlatformBody } from '~/queries/platforms';
import { InputControlled } from '~/components/InputControlled';

type Props = { open: boolean; onClose: (platformId?: string) => void };

export const NewLLMDialog: FC<Props> = ({ open, onClose }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { addSnackbar } = useSnackbar();
  const [selectedProvider, setSelectedProvider] = useState<Provider>('openai');
  const form = useForm<CreateOrUpdateLLMFormSchema>({
    resolver: zodResolver(createOrUpdateLLMFormSchema),
    defaultValues: { name: '', model: OPENAI_MODEL_VALUES[0], provider: 'openai' },
    mode: 'onChange',
  });

  const mutation = useCreateLLMMutation();

  const modelItems = useMemo(() => {
    const makeItems = (values: readonly string[]) =>
      values.map((modelValue) => {
        const [providerPrefix] = modelValue.split(':');
        return { optgroup: providerPrefix.toUpperCase(), value: modelValue, label: beautifyLabel(modelValue) };
      });

    return [...makeItems(OPENAI_MODEL_VALUES), ...makeItems(AZURE_MODEL_VALUES), ...makeItems(BEDROCK_MODEL_VALUES)];
  }, []);

  const onSubmit = form.handleSubmit((values) => {
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
      credentials: Object.keys(credentials).length ? credentials : undefined,
    };

    mutation.mutate(
      { tenantId, body: payload },
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
      <Form onSubmit={onSubmit}>
        <FormProvider {...form}>
          <Dialog.Header>
            <Dialog.Header.Title title="New Large Language Model (LLM)" />
            <Dialog.Header.Description>
              Agents need LLMs to function, and you can configure an agent to use any configured LLM during deployment.
            </Dialog.Header.Description>
          </Dialog.Header>
          <Dialog.Content>
            <Box p="$4">
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
                        const [providerPrefix] = String(selectedModel).split(':');
                        if (providerPrefix === 'openai' || providerPrefix === 'azure' || providerPrefix === 'bedrock') {
                          setSelectedProvider(providerPrefix);
                          form.setValue('provider', providerPrefix);
                        }
                      }}
                    />
                  )}
                />

                {selectedProvider === 'openai' && (
                  <InputControlled
                    fieldName="apiKey"
                    label="OpenAI API Key"
                    type="password"
                    placeholder="Enter API key"
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
                    <InputControlled fieldName="apiKey" label="Azure API Key" type="password" />
                  </Box>
                )}

                {selectedProvider === 'bedrock' && (
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
            </Box>
          </Dialog.Content>
          <Dialog.Actions>
            <Button variant="primary" type="submit" round disabled={mutation.isPending}>
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

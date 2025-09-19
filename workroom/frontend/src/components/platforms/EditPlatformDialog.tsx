import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Checkbox, Dialog, Form, Input, Select, useSnackbar } from '@sema4ai/components';
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
import { type PlatformForEditing } from '~/queries/agent-interface-patches';
import { beautifyLabel } from '~/lib/utils';

type Props = {
  open: boolean;
  onClose: () => void;
  onUpdated?: (platform: GetPlatformResponse) => void;
  platform: PlatformForEditing;
  tenantId: string;
};

export const EditPlatformDialog: FC<Props> = ({ platform, open, onClose, onUpdated, tenantId }) => {
  const { addSnackbar } = useSnackbar();
  const kind: Provider = platform.kind;

  const firstModel = platform.models?.[kind]?.[0];
  const currentModel = firstModel ? `${kind}:${firstModel}` : `${kind}:unknown`;

  const getPlatformConfig = () => {
    const base = { name: platform.name, provider: kind, model: currentModel, validateLLM: true };

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
    };
  };

  const form = useForm<EditLLMFormSchema>({
    resolver: zodResolver(editLLMFormSchema),
    defaultValues: getPlatformConfig(),
    mode: 'onChange',
  });

  const isAzure = kind === 'azure';
  const isBedrock = kind === 'bedrock';

  const mutation = useUpdateLLMMutation();

  const onSubmit = form.handleSubmit((values) => {
    const [, modelId] = String(values.model).split(':');

    const credentials: Record<string, unknown> = {};

    if (kind === 'azure') {
      if (values.apiKey) credentials.azure_api_key = values.apiKey;
      if (values.azure_endpoint_url) credentials.azure_endpoint_url = values.azure_endpoint_url;
      if (values.azure_api_version) credentials.azure_api_version = values.azure_api_version;
      if (values.azure_deployment_name) credentials.azure_deployment_name = values.azure_deployment_name;
    } else if (kind === 'bedrock') {
      if (values.aws_access_key_id) credentials.aws_access_key_id = values.aws_access_key_id;
      if (values.aws_secret_access_key) credentials.aws_secret_access_key = values.aws_secret_access_key;
      if (values.region_name) credentials.region_name = values.region_name;
    } else if (kind === 'openai') {
      if (values.apiKey) credentials.openai_api_key = values.apiKey;
    } else {
      kind satisfies never;
    }

    const payload = {
      id: platform.platform_id,
      name: values.name,
      kind: kind,
      models: { [kind]: [modelId] },
      credentials: Object.keys(credentials).length ? credentials : undefined,
    } satisfies UpdatePlatformBody;

    mutation.mutate(
      { tenantId, platformId: platform.platform_id, validateLLM: values.validateLLM, body: payload },
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
        .map((modelValue) => ({ value: modelValue, label: beautifyLabel(modelValue) }));
    if (kind === 'azure') return forProvider(AZURE_MODEL_VALUES);
    if (kind === 'bedrock') return forProvider(BEDROCK_MODEL_VALUES);
    if (kind === 'openai') return forProvider(OPENAI_MODEL_VALUES);
    else {
      kind satisfies never;
      return [];
    }
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
            <Button variant="primary" round type="submit" loading={mutation.isPending}>
              Save
            </Button>
            <Button variant="outline" round type="button" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
          </Dialog.Actions>
        </FormProvider>
      </Form>
    </Dialog>
  );
};

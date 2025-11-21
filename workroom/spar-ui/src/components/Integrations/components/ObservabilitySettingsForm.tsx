import { useFormContext } from 'react-hook-form';
import { Divider, Form, Select } from '@sema4ai/components';
import { ObservabilitySettings } from '../../../queries/integrations';
import { ObservabilitySettingsFormSchema } from './observabilitySettingsSchema';
import { InputControlled } from '../../../common/form/InputControlled';
import { KeyValueRecordField } from '../../../common/form/SchemaFormFields/components/KeyValueRecordField';

type ObservabilityProviderOption = {
  value: ObservabilitySettings['provider'];
  label: string;
};

const observabilityProviderOptions: ObservabilityProviderOption[] = [
  { value: 'langsmith', label: 'Langsmith' },
  { value: 'grafana', label: 'Grafana' },
];

const LangsmithSettingsFields = () => {
  return (
    <>
      <InputControlled fieldName="url" label="URL" description="LangSmith OTLP endpoint" />

      <InputControlled fieldName="project_name" label="Project Name" description="LangSmith project name" />

      <InputControlled fieldName="api_key" label="API Key" description="LangSmith API key" type="password" />
    </>
  );
};

export const GrafanaSettingsFields = () => {
  return (
    <>
      <InputControlled fieldName="url" label="URL" description="Grafana OTLP endpoint" />

      <InputControlled fieldName="grafana_instance_id" label="Grafana Instance ID" description="Grafana instance ID" />

      <InputControlled fieldName="api_token" label="API Token" description="Grafana API token" type="password" />

      <KeyValueRecordField
        fieldName="additional_headers"
        label="Additional Headers"
        description="Optional HTTP headers to send with the request to Grafana Cloud"
        isOptional
      />
    </>
  );
};

type Props = {
  defaultValues?: ObservabilitySettingsFormSchema;
};

export const ObservabilitySettingsForm = ({ defaultValues }: Props) => {
  const { watch, reset } = useFormContext<ObservabilitySettingsFormSchema>();
  const { provider } = watch();

  return (
    <Form.Fieldset>
      <Select
        aria-label="Vendor"
        label="Vendor"
        description="Name of the OTEL vendor"
        items={observabilityProviderOptions}
        value={provider}
        onChange={(value) => {
          if (defaultValues && value === defaultValues.provider) {
            reset(defaultValues);
          } else {
            reset({ provider: value as ObservabilitySettings['provider'], url: '' });
          }
        }}
      />

      <Divider />

      {provider === 'langsmith' && <LangsmithSettingsFields />}
      {provider === 'grafana' && <GrafanaSettingsFields />}

      {!!provider && <Divider />}
    </Form.Fieldset>
  );
};

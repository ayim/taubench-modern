import { useFormContext } from 'react-hook-form';
import { Divider, Form, Select } from '@sema4ai/components';
import { ObservabilitySettings } from '../../../queries/integrations';
import { ObservabilitySettingsFormSchema } from './observabilitySettingsSchema';
import { InputControlled } from '../../../common/form/InputControlled';
import { KeyValueRecordField } from '../../../common/form/SchemaFormFields/components/KeyValueRecordField';

type ObservabilityKindOption = {
  value: ObservabilitySettings['kind'];
  label: string;
};

const observabilityKindOptions: ObservabilityKindOption[] = [
  { value: 'langsmith', label: 'Langsmith' },
  { value: 'grafana', label: 'Grafana' },
];

const LangsmithSettingsFields = () => {
  return (
    <>
      <InputControlled fieldName="provider_settings.url" label="URL" description="LangSmith OTLP endpoint" />

      <InputControlled
        fieldName="provider_settings.project_name"
        label="Project Name"
        description="LangSmith project name"
      />

      <InputControlled
        fieldName="provider_settings.api_key"
        label="API Key"
        description="LangSmith API key"
        type="password"
      />
    </>
  );
};

export const GrafanaSettingsFields = () => {
  return (
    <>
      <InputControlled fieldName="provider_settings.url" label="URL" description="Grafana OTLP endpoint" />

      <InputControlled
        fieldName="provider_settings.grafana_instance_id"
        label="Grafana Instance ID"
        description="Grafana instance ID"
      />

      <InputControlled
        fieldName="provider_settings.api_token"
        label="API Token"
        description="Grafana API token"
        type="password"
      />

      <KeyValueRecordField
        fieldName="provider_settings.additional_headers"
        label="Additional Headers"
        description="Optional HTTP headers to send with the request to Grafana Cloud"
        isOptional
      />
    </>
  );
};

export const ObservabilitySettingsForm = () => {
  const { watch, reset } = useFormContext<ObservabilitySettingsFormSchema>();
  const { kind } = watch();

  return (
    <Form.Fieldset>
      <Select
        aria-label="Vendor"
        label="Vendor"
        description="Name of the OTEL vendor"
        items={observabilityKindOptions}
        value={kind}
        onChange={(value) => {
          reset({ kind: value as ObservabilitySettings['kind'], provider_settings: {} });
        }}
      />

      <Divider />

      {kind === 'langsmith' && <LangsmithSettingsFields />}
      {kind === 'grafana' && <GrafanaSettingsFields />}

      {!!kind && <Divider />}
    </Form.Fieldset>
  );
};

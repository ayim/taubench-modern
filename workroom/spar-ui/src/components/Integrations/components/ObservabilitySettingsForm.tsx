import { useFormContext } from 'react-hook-form';
import { Banner, Divider, Form, Select, Switch } from '@sema4ai/components';
import { IconSnowflake } from '@sema4ai/icons/logos';
import { useSparUIContext } from '../../../api/context';
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
  const { platformConfig } = useSparUIContext();
  const { watch, reset, setValue } = useFormContext<ObservabilitySettingsFormSchema>();
  const { provider, is_enabled: isEnabled } = watch();
  const snowflakeEAIUrl = platformConfig?.snowflakeEAIUrl ?? null;

  return (
    <Form.Fieldset>
      <Switch
        label="Enabled"
        description="Enable or disable observability"
        checked={isEnabled}
        onChange={(e) => {
          const enabled = e.target.checked;
          /**
           * If we are editing an existing integration, we want to reset the form to the default values
           * when it's being disabled.
           */
          if (!enabled && defaultValues) {
            reset(defaultValues);
          }

          setValue('is_enabled', enabled);
        }}
      />

      {defaultValues?.is_enabled && isEnabled && snowflakeEAIUrl && (
        <Banner
          message="Snowflake EAI Update Necessary"
          description={
            <span>
              Specifying an observability data destination will require updating EAI rules for this application. Follow{' '}
              <a href={snowflakeEAIUrl} target="_blank" rel="noreferrer">
                these instructions
              </a>{' '}
              to update your EAI configuration.
            </span>
          }
          variant="info"
          icon={IconSnowflake}
        />
      )}

      <Select
        aria-label="Vendor"
        label="Vendor"
        description="Name of the OTEL vendor"
        items={observabilityProviderOptions}
        value={provider}
        disabled={!isEnabled}
        onChange={(value) => {
          if (defaultValues && value === defaultValues.provider) {
            reset(defaultValues);
          } else {
            reset({ provider: value as ObservabilitySettings['provider'], url: '', is_enabled: true });
          }
        }}
      />

      <Divider />

      {isEnabled && (
        <>
          {provider === 'langsmith' && <LangsmithSettingsFields />}
          {provider === 'grafana' && <GrafanaSettingsFields />}

          {!!provider && <Divider />}
        </>
      )}
    </Form.Fieldset>
  );
};

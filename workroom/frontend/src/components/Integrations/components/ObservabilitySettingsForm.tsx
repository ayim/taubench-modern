import { useMemo } from 'react';
import { useFormContext } from 'react-hook-form';
import { Banner, Divider, Form, Select, Switch } from '@sema4ai/components';
import { IconSnowflake } from '@sema4ai/icons/logos';
import { ObservabilitySettings } from '~/queries/integrations';
import { InputControlled } from '~/components/form/InputControlled';
import { KeyValueRecordField } from '~/components/form/SchemaFormFields/components/KeyValueRecordField';
import { ObservabilitySettingsFormSchema } from './observabilitySettingsSchema';
import { useSparUIContext } from '../../../api/context';

type ObservabilityProviderOption = {
  value: ObservabilitySettings['provider'];
  label: string;
};

const observabilityProviderOptions: ObservabilityProviderOption[] = [
  { value: 'langsmith', label: 'Langsmith' },
  { value: 'grafana', label: 'Grafana Cloud' },
  { value: 'otlp_basic_auth', label: 'OTLP (Username/Password)' },
  { value: 'otlp_custom_headers', label: 'OTLP (Custom Headers)' },
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

const OtlpBasicAuthSettingsFields = () => {
  return (
    <>
      <InputControlled fieldName="url" label="URL" description="OTLP endpoint URL" />

      <InputControlled fieldName="username" label="Username" description="Basic auth username" />

      <InputControlled fieldName="password" label="Password" description="Basic auth password" type="password" />
    </>
  );
};

const OtlpCustomHeadersSettingsFields = () => {
  return (
    <>
      <InputControlled fieldName="url" label="URL" description="OTLP endpoint URL" />

      <KeyValueRecordField
        fieldName="headers"
        label="Headers"
        description="Custom HTTP headers to send with the request"
        isOptional={false}
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

  const providerSettingsFields = useMemo(() => {
    switch (provider) {
      case 'langsmith':
        return <LangsmithSettingsFields />;
      case 'grafana':
        return <GrafanaSettingsFields />;
      case 'otlp_basic_auth':
        return <OtlpBasicAuthSettingsFields />;
      case 'otlp_custom_headers':
        return <OtlpCustomHeadersSettingsFields />;
      case undefined:
        return null;
      default:
        provider satisfies never;
        return null;
    }
  }, [provider]);

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
            return;
          }

          switch (value) {
            case 'langsmith':
              reset({ provider: 'langsmith', url: '', is_enabled: true, project_name: '', api_key: '' });
              break;
            case 'grafana':
              reset({ provider: 'grafana', url: '', is_enabled: true, api_token: '', grafana_instance_id: '' });
              break;
            case 'otlp_basic_auth':
              reset({ provider: 'otlp_basic_auth', url: '', is_enabled: true, username: '', password: '' });
              break;
            case 'otlp_custom_headers':
              reset({ provider: 'otlp_custom_headers', url: '', is_enabled: true, headers: {} });
              break;
            default:
              break;
          }
        }}
      />

      <Divider />

      {isEnabled && (
        <>
          {providerSettingsFields}
          {!!provider && <Divider />}
        </>
      )}
    </Form.Fieldset>
  );
};

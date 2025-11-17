import { z } from 'zod';
import { ObservabilityProviderSettings, ObservabilitySettings } from '../../../queries/integrations';
import { apiSecretValueToString } from '../../../common/helpers';

export const otelProviders: ObservabilitySettings['kind'][] = ['langsmith', 'grafana'];

export const observabilitySettingsSchema = z
  .object({
    kind: z.enum(otelProviders),
    provider_settings: z.object({
      url: z.url(),
      project_name: z.string().optional(),
      api_key: z.string().optional(),
      api_token: z.string().optional(),
      grafana_instance_id: z.string().optional(),
      additional_headers: z.record(z.string(), z.string()).optional(),
    }),
  })
  .superRefine((values, ctx) => {
    if (values.kind === 'langsmith') {
      if (!values.provider_settings.project_name) {
        ctx.addIssue({
          code: 'custom',
          path: ['provider_settings', 'project_name'],
          message: 'Project name is required',
        });
      }
      if (!values.provider_settings.api_key) {
        ctx.addIssue({
          code: 'custom',
          path: ['provider_settings', 'api_key'],
          message: 'API key is required',
        });
      }
    }

    if (values.kind === 'grafana') {
      if (!values.provider_settings.api_token) {
        ctx.addIssue({
          code: 'custom',
          path: ['provider_settings', 'api_token'],
          message: 'API token is required',
        });
      }
      if (!values.provider_settings.grafana_instance_id) {
        ctx.addIssue({
          code: 'custom',
          path: ['provider_settings', 'grafana_instance_id'],
          message: 'Grafana instance ID is required',
        });
      }
    }
  });

export type ObservabilitySettingsFormSchema = z.infer<typeof observabilitySettingsSchema>;

export const apiResponseToFormValues = (data: ObservabilitySettings): ObservabilitySettingsFormSchema => {
  const providerSettings = (data.provider_settings || {}) as ObservabilityProviderSettings;

  return {
    kind: data.kind,
    provider_settings: {
      url: providerSettings.url,
      project_name: providerSettings.project_name,
      api_key: apiSecretValueToString(providerSettings.api_key || ''),
      api_token: apiSecretValueToString(providerSettings.api_token || ''),
      grafana_instance_id: providerSettings.grafana_instance_id || '',
      additional_headers: providerSettings.additional_headers || undefined,
    },
  };
};

export const toObservabilitySettings = (data: ObservabilitySettingsFormSchema): ObservabilitySettings => {
  if (data.kind === 'langsmith') {
    return {
      is_enabled: true,
      kind: data.kind,
      provider_settings: {
        url: data.provider_settings.url || '',
        api_key: data.provider_settings.api_key || '',
        project_name: data.provider_settings.project_name || '',
      },
    };
  }

  if (data.kind === 'grafana') {
    return {
      is_enabled: true,
      kind: data.kind,
      provider_settings: {
        url: data.provider_settings.url || '',
        api_token: data.provider_settings.api_token || '',
        grafana_instance_id: data.provider_settings.grafana_instance_id || '',
        additional_headers: data.provider_settings.additional_headers || {},
      },
    };
  }

  throw new Error('Invalid observability provider');
};

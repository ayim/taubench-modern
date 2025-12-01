import { z } from 'zod';
import { ObservabilitySettings } from '../../../queries/integrations';
import { apiSecretValueToString } from '../../../common/helpers';

export const otelProviders = ['langsmith', 'grafana'] as const;

export const observabilitySettingsSchema = z
  .object({
    is_enabled: z.boolean(),
    provider: z.enum(otelProviders),
    url: z.url(),
    // LangSmith fields
    project_name: z.string().optional(),
    api_key: z.string().optional(),
    // Grafana fields
    api_token: z.string().optional(),
    grafana_instance_id: z.string().optional(),
    additional_headers: z.record(z.string(), z.string()).optional(),
  })
  .superRefine((values, ctx) => {
    if (values.provider === 'langsmith') {
      if (!values.project_name) {
        ctx.addIssue({
          code: 'custom',
          path: ['project_name'],
          message: 'Project name is required',
        });
      }
      if (!values.api_key) {
        ctx.addIssue({
          code: 'custom',
          path: ['api_key'],
          message: 'API key is required',
        });
      }
    }

    if (values.provider === 'grafana') {
      if (!values.api_token) {
        ctx.addIssue({
          code: 'custom',
          path: ['api_token'],
          message: 'API token is required',
        });
      }
      if (!values.grafana_instance_id) {
        ctx.addIssue({
          code: 'custom',
          path: ['grafana_instance_id'],
          message: 'Grafana instance ID is required',
        });
      }
    }
  });

export type ObservabilitySettingsFormSchema = z.infer<typeof observabilitySettingsSchema>;

export const apiResponseToFormValues = (data: ObservabilitySettings): ObservabilitySettingsFormSchema => {
  const baseFormValues: ObservabilitySettingsFormSchema = {
    is_enabled: data.is_enabled,
    provider: data.provider,
    url: data.url,
  };

  // Handle discriminated union properly
  if (data.provider === 'langsmith') {
    return {
      ...baseFormValues,
      project_name: data.project_name,
      api_key: apiSecretValueToString(data.api_key),
    };
  }

  if (data.provider === 'grafana') {
    return {
      ...baseFormValues,
      api_token: apiSecretValueToString(data.api_token),
      grafana_instance_id: data.grafana_instance_id,
      additional_headers: data.additional_headers || undefined,
    };
  }

  throw new Error(`Unknown observability provider`);
};

export const toObservabilitySettings = (data: ObservabilitySettingsFormSchema): ObservabilitySettings => {
  if (data.provider === 'langsmith') {
    return {
      is_enabled: data.is_enabled,
      provider: data.provider,
      url: data.url || '',
      api_key: data.api_key || '',
      project_name: data.project_name || '',
    };
  }

  if (data.provider === 'grafana') {
    return {
      is_enabled: data.is_enabled,
      provider: data.provider,
      url: data.url || '',
      api_token: data.api_token || '',
      grafana_instance_id: data.grafana_instance_id || '',
      additional_headers: data.additional_headers || {},
    };
  }

  throw new Error('Invalid observability provider');
};

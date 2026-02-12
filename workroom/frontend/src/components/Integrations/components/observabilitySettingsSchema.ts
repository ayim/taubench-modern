import { z } from 'zod';
import { ObservabilitySettings } from '~/queries/integrations';
import { apiSecretValueToString } from '~/components/helpers';

export const otelProviders = ['langsmith', 'grafana', 'otlp_basic_auth', 'otlp_custom_headers'] as const;

export const traceUITypeEnum = z.enum(['grafana', 'jaeger', 'unknown']);
export type TraceUIType = z.infer<typeof traceUITypeEnum>;

export const observabilitySettingsSchema = z.discriminatedUnion('provider', [
  z.object({
    is_enabled: z.boolean(),
    provider: z.literal('langsmith'),
    url: z.string().url('Invalid URL'),
    project_name: z.string().min(1, 'Project name is required'),
    api_key: z.string().min(1, 'API key is required'),
  }),
  z.object({
    is_enabled: z.boolean(),
    provider: z.literal('grafana'),
    url: z.string().url('Invalid URL'),
    api_token: z.string().min(1, 'API token is required'),
    grafana_instance_id: z.string().min(1, 'Grafana instance ID is required'),
    additional_headers: z.record(z.string(), z.string()).optional(),
  }),
  z.object({
    is_enabled: z.boolean(),
    provider: z.literal('otlp_basic_auth'),
    url: z.string().url('Invalid URL'),
    username: z.string().min(1, 'Username is required'),
    password: z.string().min(1, 'Password is required'),
    trace_ui_type: traceUITypeEnum,
  }),
  z.object({
    is_enabled: z.boolean(),
    provider: z.literal('otlp_custom_headers'),
    url: z.string().url('Invalid URL'),
    headers: z.record(z.string(), z.string()).refine((headers) => Object.keys(headers).length > 0, {
      message: 'At least one header is required',
    }),
    trace_ui_type: traceUITypeEnum,
  }),
]);

export type ObservabilitySettingsFormSchema = z.infer<typeof observabilitySettingsSchema>;

export const apiResponseToFormValues = (data: ObservabilitySettings): ObservabilitySettingsFormSchema => {
  switch (data.provider) {
    case 'langsmith':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        project_name: data.project_name,
        api_key: apiSecretValueToString(data.api_key),
      };
    case 'grafana':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        api_token: apiSecretValueToString(data.api_token),
        grafana_instance_id: data.grafana_instance_id,
        additional_headers: data.additional_headers ?? undefined,
      };
    case 'otlp_basic_auth':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        username: data.username,
        password: apiSecretValueToString(data.password),
        trace_ui_type: data.trace_ui_type,
      };
    case 'otlp_custom_headers':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        headers: data.headers ?? {},
        trace_ui_type: data.trace_ui_type,
      };
    default:
      data satisfies never;
      throw new Error(`Unknown observability provider`);
  }
};

export const toObservabilitySettings = (data: ObservabilitySettingsFormSchema): ObservabilitySettings => {
  switch (data.provider) {
    case 'langsmith':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        api_key: data.api_key,
        project_name: data.project_name,
      };
    case 'grafana':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        api_token: data.api_token,
        grafana_instance_id: data.grafana_instance_id,
        additional_headers: data.additional_headers ?? {},
      };
    case 'otlp_basic_auth':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        username: data.username,
        password: data.password,
        trace_ui_type: data.trace_ui_type,
      };
    case 'otlp_custom_headers':
      return {
        is_enabled: data.is_enabled,
        provider: data.provider,
        url: data.url,
        headers: data.headers,
        trace_ui_type: data.trace_ui_type,
      };
    default:
      data satisfies never;
      throw Error('Invalid observability provider');
  }
};

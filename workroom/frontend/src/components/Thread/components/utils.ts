import type { ObservabilityIntegration } from '~/queries/integrations';

/**
 * Checks if trace URL viewing is supported based on the observability integration settings.
 * Currently only OTLP providers (basic auth and custom headers) support trace URLs,
 * and the integration must be enabled with a configured trace UI type.
 *
 * Note: We currently support only one observability integration, so we check integrations[0].
 */
export const isTraceUrlSupported = (integrations?: ObservabilityIntegration[]): boolean => {
  // We currently support only one observability integration
  const settings = integrations?.[0]?.settings;
  if (!settings) return false;

  const isOTLPProvider = settings.provider === 'otlp_basic_auth' || settings.provider === 'otlp_custom_headers';

  return isOTLPProvider && settings.is_enabled && settings.trace_ui_type !== 'unknown';
};

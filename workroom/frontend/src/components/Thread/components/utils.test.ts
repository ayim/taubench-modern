import { describe, it, expect } from 'vitest';
import type { ObservabilityIntegration } from '~/queries/integrations';
import { isTraceUrlSupported } from './utils';

// Helper to create a complete integration fixture with required fields
const createIntegration = (settings: ObservabilityIntegration['settings']): ObservabilityIntegration => ({
  id: 'test-id',
  settings,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  kind: 'observability',
});

describe('isTraceUrlSupported', () => {
  it('returns false when integrations is undefined', () => {
    expect(isTraceUrlSupported(undefined)).toBe(false);
  });

  it('returns false when integrations array is empty', () => {
    expect(isTraceUrlSupported([])).toBe(false);
  });

  it('returns false for langsmith provider (unsupported)', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'langsmith',
        url: 'https://api.smith.langchain.com',
        project_name: 'test',
        api_key: 'secret',
        is_enabled: true,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(false);
  });

  it('returns false for grafana provider (unsupported)', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'grafana',
        url: 'https://grafana.example.com',
        api_token: 'secret',
        grafana_instance_id: 'instance-123',
        is_enabled: true,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(false);
  });

  it('returns false for otlp_basic_auth when trace_ui_type is unknown', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'otlp_basic_auth',
        url: 'https://otlp.example.com',
        username: 'user',
        password: 'pass',
        trace_ui_type: 'unknown',
        is_enabled: true,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(false);
  });

  it('returns false for otlp_basic_auth when is_enabled is false', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'otlp_basic_auth',
        url: 'https://otlp.example.com',
        username: 'user',
        password: 'pass',
        trace_ui_type: 'grafana',
        is_enabled: false,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(false);
  });

  it('returns true for otlp_basic_auth with grafana trace_ui_type and enabled', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'otlp_basic_auth',
        url: 'https://otlp.example.com',
        username: 'user',
        password: 'pass',
        trace_ui_type: 'grafana',
        is_enabled: true,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(true);
  });

  it('returns true for otlp_basic_auth with jaeger trace_ui_type and enabled', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'otlp_basic_auth',
        url: 'https://otlp.example.com',
        username: 'user',
        password: 'pass',
        trace_ui_type: 'jaeger',
        is_enabled: true,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(true);
  });

  it('returns true for otlp_custom_headers with grafana trace_ui_type and enabled', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'otlp_custom_headers',
        url: 'https://otlp.example.com',
        headers: { Authorization: 'Bearer token' },
        trace_ui_type: 'grafana',
        is_enabled: true,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(true);
  });

  it('returns false for otlp_custom_headers when trace_ui_type is unknown', () => {
    const integrations: ObservabilityIntegration[] = [
      createIntegration({
        provider: 'otlp_custom_headers',
        url: 'https://otlp.example.com',
        headers: { Authorization: 'Bearer token' },
        trace_ui_type: 'unknown',
        is_enabled: true,
      }),
    ];
    expect(isTraceUrlSupported(integrations)).toBe(false);
  });
});

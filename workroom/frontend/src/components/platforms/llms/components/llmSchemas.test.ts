import { describe, it, expect, vi } from 'vitest';
import {
  getAzureFoundryModelFamily,
  getAzureFoundryModelId,
  getModelFamilyFromPlatform,
  AZURE_FOUNDRY_MODEL_VALUES,
  createOrUpdateLLMFormSchema,
} from './llmSchemas';

// Mock the router import as it causes test run fails
vi.mock('~/components/providers/Router', () => ({
  router: {
    flatRoutes: [],
  },
}));

describe('getAzureFoundryModelFamily', () => {
  it('extracts anthropic from azure_foundry:anthropic:claude-4-5-sonnet', () => {
    expect(getAzureFoundryModelFamily('azure_foundry:anthropic:claude-4-5-sonnet')).toBe('anthropic');
  });

  it('extracts anthropic from azure_foundry:anthropic:claude-4-5-opus-thinking-high', () => {
    expect(getAzureFoundryModelFamily('azure_foundry:anthropic:claude-4-5-opus-thinking-high')).toBe('anthropic');
  });

  it('extracts openai from azure_foundry:openai:gpt-4o', () => {
    expect(getAzureFoundryModelFamily('azure_foundry:openai:gpt-4o')).toBe('openai');
  });

  it('throws for non-azure_foundry models', () => {
    expect(() => getAzureFoundryModelFamily('openai:gpt-4')).toThrow('Invalid Azure Foundry model value');
  });

  it('throws for invalid format with only two segments', () => {
    expect(() => getAzureFoundryModelFamily('azure_foundry:claude')).toThrow('Invalid Azure Foundry model value');
  });
});

describe('getAzureFoundryModelId', () => {
  it('extracts model id from azure_foundry:anthropic:claude-4-5-sonnet', () => {
    expect(getAzureFoundryModelId('azure_foundry:anthropic:claude-4-5-sonnet')).toBe('claude-4-5-sonnet');
  });

  it('extracts model id from thinking model', () => {
    expect(getAzureFoundryModelId('azure_foundry:anthropic:claude-4-5-opus-thinking-high')).toBe(
      'claude-4-5-opus-thinking-high',
    );
  });

  it('returns undefined for non-azure_foundry models', () => {
    expect(getAzureFoundryModelId('openai:gpt-4')).toBeUndefined();
  });
});

describe('getModelFamilyFromPlatform', () => {
  it('returns anthropic when models contain anthropic key', () => {
    expect(getModelFamilyFromPlatform({ anthropic: ['claude-4-5-sonnet'] })).toBe('anthropic');
  });

  it('returns openai when models contain openai key', () => {
    expect(getModelFamilyFromPlatform({ openai: ['gpt-4o'] })).toBe('openai');
  });

  it('returns undefined for empty models', () => {
    expect(getModelFamilyFromPlatform({})).toBeUndefined();
  });
});

describe('AZURE_FOUNDRY_MODEL_VALUES', () => {
  it('all values follow triple-segment format', () => {
    AZURE_FOUNDRY_MODEL_VALUES.forEach((value) => {
      const parts = value.split(':');
      expect(parts).toHaveLength(3);
      expect(parts[0]).toBe('azure_foundry');
      expect(['anthropic', 'openai']).toContain(parts[1]);
      expect(parts[2]).toBeTruthy();
    });
  });

  it('includes both openai and anthropic models', () => {
    const families = new Set(AZURE_FOUNDRY_MODEL_VALUES.map((v) => v.split(':')[1]));
    expect(families).toContain('openai');
    expect(families).toContain('anthropic');
  });
});

describe('createOrUpdateLLMFormSchema - azure_foundry validation', () => {
  it('requires azure_foundry_endpoint_url for azure_foundry platform', () => {
    const result = createOrUpdateLLMFormSchema.safeParse({
      platform: 'azure_foundry',
      validateLLM: true,
      name: 'Test LLM',
      model: 'azure_foundry:anthropic:claude-4-5-sonnet',
      azure_foundry_api_key: 'test-key',
      azure_foundry_deployment_name: 'test-deployment',
      // missing azure_foundry_endpoint_url
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      const endpointUrlError = result.error.issues.find((issue) => issue.path.includes('azure_foundry_endpoint_url'));
      expect(endpointUrlError).toBeDefined();
      expect(endpointUrlError?.message).toBe('Endpoint URL is required');
    }
  });

  it('requires azure_foundry_api_key for azure_foundry platform', () => {
    const result = createOrUpdateLLMFormSchema.safeParse({
      platform: 'azure_foundry',
      validateLLM: true,
      name: 'Test LLM',
      model: 'azure_foundry:anthropic:claude-4-5-sonnet',
      azure_foundry_endpoint_url: 'https://test.services.ai.azure.com',
      azure_foundry_deployment_name: 'test-deployment',
      // missing azure_foundry_api_key
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      const apiKeyError = result.error.issues.find((issue) => issue.path.includes('azure_foundry_api_key'));
      expect(apiKeyError).toBeDefined();
      expect(apiKeyError?.message).toBe('API key is required');
    }
  });

  it('requires azure_foundry_deployment_name for azure_foundry platform', () => {
    const result = createOrUpdateLLMFormSchema.safeParse({
      platform: 'azure_foundry',
      validateLLM: true,
      name: 'Test LLM',
      model: 'azure_foundry:anthropic:claude-4-5-sonnet',
      azure_foundry_endpoint_url: 'https://test.services.ai.azure.com',
      azure_foundry_api_key: 'test-key',
      // missing azure_foundry_deployment_name
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      const deploymentError = result.error.issues.find((issue) => issue.path.includes('azure_foundry_deployment_name'));
      expect(deploymentError).toBeDefined();
      expect(deploymentError?.message).toBe('Deployment name is required');
    }
  });

  it('validates successfully with all required azure_foundry fields', () => {
    const result = createOrUpdateLLMFormSchema.safeParse({
      platform: 'azure_foundry',
      validateLLM: true,
      name: 'Test LLM',
      model: 'azure_foundry:anthropic:claude-4-5-sonnet',
      azure_foundry_endpoint_url: 'https://test.services.ai.azure.com',
      azure_foundry_api_key: 'test-key',
      azure_foundry_deployment_name: 'test-deployment',
    });

    expect(result.success).toBe(true);
  });

  it('requires api_version for OpenAI family models', () => {
    const result = createOrUpdateLLMFormSchema.safeParse({
      platform: 'azure_foundry',
      validateLLM: true,
      name: 'Test LLM',
      model: 'azure_foundry:openai:gpt-4o',
      azure_foundry_endpoint_url: 'https://test.services.ai.azure.com',
      azure_foundry_api_key: 'test-key',
      azure_foundry_deployment_name: 'test-deployment',
      // missing azure_foundry_api_version - required for openai
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      const apiVersionError = result.error.issues.find((issue) => issue.path.includes('azure_foundry_api_version'));
      expect(apiVersionError).toBeDefined();
      expect(apiVersionError?.message).toBe('API version is required for OpenAI models');
    }
  });
});

describe('Field name consistency', () => {
  /**
   * CRITICAL: These field names must match what the backend expects.
   * If these tests fail, there's a mismatch between frontend and backend field names.
   */
  it('uses snake_case for azure_foundry field names', () => {
    // These field names must match what backend expects
    const validData = {
      platform: 'azure_foundry',
      validateLLM: true,
      name: 'Test',
      model: 'azure_foundry:anthropic:claude-4-5-sonnet',
      azure_foundry_endpoint_url: 'https://test.services.ai.azure.com',
      azure_foundry_api_key: 'key',
      azure_foundry_deployment_name: 'deployment',
    };

    const result = createOrUpdateLLMFormSchema.safeParse(validData);
    expect(result.success).toBe(true);

    // If we accidentally used camelCase, the schema would reject it
    const invalidCamelCase = {
      platform: 'azure_foundry',
      validateLLM: true,
      name: 'Test',
      model: 'azure_foundry:anthropic:claude-4-5-sonnet',
      azureFoundryEndpointUrl: 'https://test.services.ai.azure.com', // Wrong! Should be snake_case
      azureFoundryApiKey: 'key',
    };

    const invalidResult = createOrUpdateLLMFormSchema.safeParse(invalidCamelCase);
    // This should fail because camelCase fields aren't recognized
    // and required snake_case fields are missing
    expect(invalidResult.success).toBe(false);
  });
});

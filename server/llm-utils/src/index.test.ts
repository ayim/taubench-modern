import { testLLMConfiguration } from '.';
import { testAzureConfiguration } from './azure';
import { AzureLLMModelValueName, ModelConfigurationType } from './azure/types';
import { OpenAIModelValueName } from './openAI/types';
import { AmazonLLMModelValueName } from './amazon/types';
import { BedrockRuntimeClient } from '@aws-sdk/client-bedrock-runtime';
import { testAmazonConfiguration } from './amazon';
import { BedrockRuntimeServiceException } from '@aws-sdk/client-bedrock-runtime';

describe('testLLMConfiguration - OpenAI', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should fail validation with missing API key', async () => {
    const mockOpenAIConfig = {
      provider: 'OpenAI' as const,
      model: OpenAIModelValueName.GPT_4O,
      config: {},
    };

    // @ts-expect-error - openai_api_key not set to test validation error
    const result = await testLLMConfiguration(mockOpenAIConfig);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'LLM_CONFIG_VALIDATION_ERROR',
        message: 'Missing OpenAI API key',
        fields: ['openai_api_key'],
      },
    });
  });

  it('should fail with invalid API key', async () => {
    const mockOpenAIConfig = {
      provider: 'OpenAI' as const,
      model: OpenAIModelValueName.GPT_4O,
      config: {
        openai_api_key: 'invalid-api-key',
        temperature: 0.5,
      },
    };

    const result = await testLLMConfiguration(mockOpenAIConfig);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Invalid API key',
        fields: ['openai_api_key'],
      },
    });
  });
});

describe('testAzureConfiguration', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it('should fail validation with missing fields - missing chat_url', async () => {
    const config = {
      provider: 'Azure' as const,
      model: AzureLLMModelValueName.GPT_4_AZURE,
      type: ModelConfigurationType.LLM,
      config: {
        chat_openai_api_key: '',
      },
    };

    const result = await testAzureConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'LLM_CONFIG_VALIDATION_ERROR',
        message: 'Validation error, missing fields',
        fields: ['chat_url', 'chat_openai_api_key'],
      },
    });
  });

  it('should fail with invalid API key', async () => {
    const config = {
      provider: 'Azure' as const,
      model: AzureLLMModelValueName.GPT_4_AZURE,
      type: ModelConfigurationType.Embedding,
      config: {
        embeddings_url: 'https://example.com/embeddings',
        embeddings_openai_api_key: 'invalid-api-key',
      },
    };

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
    });

    const result = await testAzureConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Invalid API key',
        fields: ['embeddings_openai_api_key'],
      },
    });
  });

  it('should fail with invalid Endpoint URL', async () => {
    const config = {
      provider: 'Azure' as const,
      model: AzureLLMModelValueName.GPT_4_AZURE,
      type: ModelConfigurationType.LLM,
      config: {
        chat_url: 'https://invalid-url.com',
        chat_openai_api_key: 'valid-key',
      },
    };

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const result = await testAzureConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Invalid Endpoint URL',
        fields: ['chat_url'],
      },
    });
  });

  it('should handle unknown errors', async () => {
    const config = {
      provider: 'Azure' as const,
      model: AzureLLMModelValueName.GPT_4_AZURE,
      type: ModelConfigurationType.LLM,
      config: {
        chat_url: 'https://example.com',
        chat_openai_api_key: 'valid-key',
      },
    };

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    const result = await testAzureConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Unknown error. Status: 500',
        fields: [],
      },
    });
  });

  it('should handle network errors', async () => {
    const config = {
      provider: 'Azure' as const,
      model: AzureLLMModelValueName.GPT_4_AZURE,
      type: ModelConfigurationType.LLM,
      config: {
        chat_url: 'https://example.com',
        chat_openai_api_key: 'valid-key',
      },
    };

    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const result = await testAzureConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Network error or invalid endpoint URL',
        fields: [],
      },
    });
  });

  it('should return success for valid configuration', async () => {
    const config = {
      provider: 'Azure' as const,
      model: AzureLLMModelValueName.GPT_4_AZURE,
      type: ModelConfigurationType.LLM,
      config: {
        chat_url: 'https://example.com',
        chat_openai_api_key: 'valid-key',
      },
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValueOnce({ model: 'gpt-4' }),
    });

    const result = await testAzureConfiguration(config);

    expect(result).toEqual({
      success: true,
      data: {
        provider: 'Azure',
        model: 'gpt-4',
      },
    });
  });
});

jest.mock('@aws-sdk/client-bedrock-runtime');

describe('testAmazonConfiguration', () => {
  afterEach(() => {
    jest.resetAllMocks();
  });

  it('should fail validation with missing fields', async () => {
    const config = {
      provider: 'Amazon' as const,
      model: AmazonLLMModelValueName.ANTHROPIC_3_5_SONNET,
      config: {
        aws_access_key_id: 'test-key',
        // aws_secret_access_key is missing
        region_name: 'us-west-2',
      },
    };

    const result = await testAmazonConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'LLM_CONFIG_VALIDATION_ERROR',
        message: 'Validation error, missing fields',
        fields: ['aws_secret_access_key'],
      },
    });
  });

  it('should fail with invalid AWS access key ID', async () => {
    class MockBedrockRuntimeServiceException extends Error {
      constructor(message: string) {
        super(message);
        this.name = 'UnrecognizedClientException';
      }
    }

    const mockError = new MockBedrockRuntimeServiceException('UnrecognizedClientException');
    Object.setPrototypeOf(mockError, BedrockRuntimeServiceException.prototype);

    const mockSend = jest.fn().mockRejectedValue(mockError);
    (BedrockRuntimeClient as jest.Mock).mockImplementation(() => ({
      send: mockSend,
    }));

    const config = {
      provider: 'Amazon' as const,
      model: AmazonLLMModelValueName.ANTHROPIC_3_5_SONNET,
      config: {
        aws_access_key_id: 'invalid-key',
        aws_secret_access_key: 'valid-secret',
        region_name: 'us-west-2',
      },
    };

    const result = await testAmazonConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Invalid AWS access key ID',
        fields: ['aws_access_key_id'],
      },
    });
  });

  it('should fail with invalid AWS secret access key', async () => {
    class MockBedrockRuntimeServiceException extends Error {
      constructor(message: string) {
        super(message);
        this.name = 'InvalidSignatureException';
      }
    }

    const mockError = new MockBedrockRuntimeServiceException('InvalidSignatureException');
    Object.setPrototypeOf(mockError, BedrockRuntimeServiceException.prototype);

    const mockSend = jest.fn().mockRejectedValue(mockError);
    (BedrockRuntimeClient as jest.Mock).mockImplementation(() => ({
      send: mockSend,
    }));

    const config = {
      provider: 'Amazon' as const,
      model: AmazonLLMModelValueName.ANTHROPIC_3_5_SONNET,
      config: {
        aws_access_key_id: 'valid-key',
        aws_secret_access_key: 'invalid-secret',
        region_name: 'us-west-2',
      },
    };

    const result = await testAmazonConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Invalid AWS secret access key',
        fields: ['aws_secret_access_key'],
      },
    });
  });

  it('should fail with invalid AWS region', async () => {
    const mockSend = jest.fn().mockRejectedValue({
      code: 'ENOTFOUND',
    });
    (BedrockRuntimeClient as jest.Mock).mockImplementation(() => ({
      send: mockSend,
    }));

    const config = {
      provider: 'Amazon' as const,
      model: AmazonLLMModelValueName.ANTHROPIC_3_5_SONNET,
      config: {
        aws_access_key_id: 'valid-key',
        aws_secret_access_key: 'valid-secret',
        region_name: 'invalid-region',
      },
    };

    const result = await testAmazonConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Invalid AWS region',
        fields: ['region_name'],
      },
    });
  });

  it('should handle unexpected errors', async () => {
    const mockSend = jest.fn().mockRejectedValue(new Error('Unexpected error'));
    (BedrockRuntimeClient as jest.Mock).mockImplementation(() => ({
      send: mockSend,
    }));

    const config = {
      provider: 'Amazon' as const,
      model: AmazonLLMModelValueName.ANTHROPIC_3_5_SONNET,
      config: {
        aws_access_key_id: 'valid-key',
        aws_secret_access_key: 'valid-secret',
        region_name: 'us-west-2',
      },
    };

    const result = await testAmazonConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Unexpected error',
        fields: [],
      },
    });
  });

  it('should return success for valid configuration', async () => {
    const mockSend = jest.fn().mockResolvedValue({
      body: 'valid response',
    });
    (BedrockRuntimeClient as jest.Mock).mockImplementation(() => ({
      send: mockSend,
    }));

    const config = {
      provider: 'Amazon' as const,
      model: AmazonLLMModelValueName.ANTHROPIC_3_5_SONNET,
      config: {
        aws_access_key_id: 'valid-key',
        aws_secret_access_key: 'valid-secret',
        region_name: 'us-west-2',
      },
    };

    const result = await testAmazonConfiguration(config);

    expect(result).toEqual({
      success: true,
      data: {},
    });
  });

  it('should fail when response body is empty', async () => {
    const mockSend = jest.fn().mockResolvedValue({
      body: null,
    });
    (BedrockRuntimeClient as jest.Mock).mockImplementation(() => ({
      send: mockSend,
    }));

    const config = {
      provider: 'Amazon' as const,
      model: AmazonLLMModelValueName.ANTHROPIC_3_5_SONNET,
      config: {
        aws_access_key_id: 'valid-key',
        aws_secret_access_key: 'valid-secret',
        region_name: 'us-west-2',
      },
    };

    const result = await testAmazonConfiguration(config);

    expect(result).toEqual({
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Failed to validate LLM, the response body was empty',
        fields: [],
      },
    });
  });
});

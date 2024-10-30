import { validateRequiredFields } from '../utils/validation';
import { AzureLLMConfiguration, TestAzureLLMConfigurationResponse } from './types';

export const testAzureConfiguration = async (
  configuration: AzureLLMConfiguration,
): Promise<TestAzureLLMConfigurationResponse> => {
  const { type: configurationType, config, provider, model } = configuration;

  const { endpointUrl, apiKey, endpointValueKey, apiKeyValueKey } = (() => {
    if (configurationType === 'llm') {
      return {
        endpointUrl: config.chat_url,
        apiKey: config.chat_openai_api_key,
        endpointValueKey: 'chat_url' as const,
        apiKeyValueKey: 'chat_openai_api_key' as const,
      };
    }
    return {
      endpointUrl: config.embeddings_url,
      apiKey: config.embeddings_openai_api_key,
      endpointValueKey: 'embeddings_url' as const,
      apiKeyValueKey: 'embeddings_openai_api_key' as const,
    };
  })();

  const missingFields = validateRequiredFields([
    { value: endpointUrl, fieldName: endpointValueKey },
    { value: apiKey, fieldName: apiKeyValueKey },
  ]);

  if (missingFields) {
    return {
      success: false,
      error: {
        code: 'LLM_CONFIG_VALIDATION_ERROR',
        message: 'Validation error, missing fields',
        fields: missingFields,
      },
    };
  }

  let azureOpenAIResponse: {
    error?: {
      code?: string;
    };
    model?: string;
  };

  try {
    const response = await fetch(endpointUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'api-key': apiKey,
      },
      body: JSON.stringify(
        configurationType === 'llm'
          ? {
              messages: [
                {
                  role: 'user',
                  content: 'test prompt',
                },
              ],
            }
          : { input: ['test message'] },
      ),
    });

    if (!response.ok) {
      if (response.status === 401) {
        return {
          success: false,
          error: {
            code: 'INVALID_LLM_CONFIG',
            message: 'Invalid API key',
            fields: [apiKeyValueKey],
          },
        };
      }

      if (response.status === 404) {
        return {
          success: false,
          error: {
            code: 'INVALID_LLM_CONFIG',
            message: 'Invalid Endpoint URL',
            fields: [endpointValueKey],
          },
        };
      }

      return {
        success: false,
        error: {
          code: 'INVALID_LLM_CONFIG',
          message: `Unknown error. Status: ${response.status}`,
          fields: [],
        },
      };
    }

    azureOpenAIResponse = await response.json();

    return {
      success: true,
      data: {
        provider,
        model: azureOpenAIResponse.model ?? model,
      },
    };
  } catch (error: unknown) {
    return {
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Network error or invalid endpoint URL',
        fields: [],
      },
    };
  }
};

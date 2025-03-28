import OpenAI from 'openai';
import { TestLLMConfigurationResponse } from '../types';
import { OpenAILLMConfiguration } from './types';

export const testOpenAiConfiguration = async (
  configuration: OpenAILLMConfiguration,
): Promise<TestLLMConfigurationResponse> => {
  if (!configuration.config.openai_api_key) {
    return {
      success: false,
      error: {
        code: 'LLM_CONFIG_VALIDATION_ERROR',
        message: 'Missing OpenAI API key',
        fields: ['openai_api_key'],
      },
    };
  }

  const openai = new OpenAI({ apiKey: configuration.config.openai_api_key });

  try {
    await openai.models.list();

    return {
      success: true,
      data: {},
    };
  } catch (error) {
    if (error instanceof OpenAI.APIError) {
      if (error.code === 'invalid_api_key') {
        return {
          success: false,
          error: {
            code: 'INVALID_LLM_CONFIG',
            message: 'Invalid API key',
            fields: ['openai_api_key'],
          },
        };
      }
    }

    return {
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: error instanceof Error ? error.message : 'Unknown error',
        fields: [],
      },
    };
  }
};

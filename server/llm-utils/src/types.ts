import { OpenAILLMConfiguration } from './openAI/types';
import { AzureLLMConfiguration } from './azure/types';
import { AmazonLLMConfiguration } from './amazon/types';

export type LLMConfiguration =
  | AzureLLMConfiguration
  | OpenAILLMConfiguration
  | AmazonLLMConfiguration;

export type TestLLMConfigurationResponse =
  | {
      success: true;
      data: Record<string, unknown>;
    }
  | {
      success: false;
      error: {
        code: 'INVALID_LLM_CONFIG' | 'LLM_CONFIG_VALIDATION_ERROR';
        message: string;
        fields: string[];
      };
    };

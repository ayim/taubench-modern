import * as ASInterface from '@sema4ai/agent-server-interface';
import { TestLLMConfigurationResponse } from '../types';

export type AzureModelInfo = ASInterface.components['schemas']['AzureGPT'] & { name: string };

export type AzureLLMConfiguration = {
  type: 'llm' | 'embedding';
  provider: 'Azure';
  model: 'gpt-4';
  config: Partial<AzureModelInfo['config']>;
};

export type TestAzureLLMConfigurationResponse =
  | {
      success: true;
      data: {
        model: string;
        provider: 'Azure';
      };
    }
  | (TestLLMConfigurationResponse & { success: false });

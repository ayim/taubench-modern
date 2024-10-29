import * as ASInterface from '@sema4ai/agent-server-interface';
import { TestLLMConfigurationResponse } from '../types';

export enum ModelConfigurationType {
  LLM = 'llm',
  Embedding = 'embedding',
}

export type AzureModelInfo = ASInterface.components['schemas']['AzureGPT'] & { name: string };

export enum AzureLLMModelValueName {
  GPT_4_AZURE = 'gpt-4',
}

export type AzureLLMConfiguration = {
  type: ModelConfigurationType;
  provider: AzureModelInfo['provider'];
  model: AzureLLMModelValueName;
  config: Partial<AzureModelInfo['config']>;
};

export type TestAzureLLMConfigurationResponse =
  | {
      success: true;
      data: {
        model: string;
        provider: AzureModelInfo['provider'];
      };
    }
  | (TestLLMConfigurationResponse & { success: false });

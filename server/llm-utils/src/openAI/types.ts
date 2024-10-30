import * as ASInterface from '@sema4ai/agent-server-interface';

export type OpenAIModelInfo = ASInterface.components['schemas']['OpenAIGPT'];

export type OpenAILLMConfiguration = {
  provider: 'OpenAI';
  model: 'gpt-3.5-turbo-1106' | 'gpt-4-turbo' | 'gpt-4o' | 'gpt-4o-mini';
  config: Omit<OpenAIModelInfo['config'], 'temperature'>;
};

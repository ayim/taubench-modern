import * as ASInterface from '@sema4ai/agent-server-interface';

export type OpenAIModelInfo = ASInterface.components['schemas']['OpenAIGPT'];

export enum OpenAIModelValueName {
  GPT_3_5_TURBO = 'gpt-3.5-turbo-1106',
  GPT_4_TURBO = 'gpt-4-turbo',
  GPT_4O = 'gpt-4o',
  GPT_4O_MINI = 'gpt-4o-mini',
}

export type OpenAILLMConfiguration = {
  provider: OpenAIModelInfo['provider'];
  model: OpenAIModelValueName;
  config: Omit<OpenAIModelInfo['config'], 'temperature'>;
};

import * as ASInterface from '@sema4ai/agent-server-interface';

export type AmazonBedrockModelInfo = ASInterface.components['schemas']['AmazonBedrock'];

export type AmazonLLMConfiguration = {
  provider: 'Amazon';
  model: 'llama3' | 'anthropic.claude-3-5-sonnet-20240620-v1:0';
  config: Partial<AmazonBedrockModelInfo['config']>;
};

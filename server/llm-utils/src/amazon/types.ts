import * as ASInterface from '@sema4ai/agent-server-interface';

export type AmazonBedrockModelInfo = ASInterface.components['schemas']['AmazonBedrock'];

export enum AmazonLLMModelValueName {
  OLLAMA = 'llama3',
  ANTHROPIC_3_5_SONNET = 'anthropic.claude-3-5-sonnet-20240620-v1:0',
}

export type AmazonLLMConfiguration = {
  provider: AmazonBedrockModelInfo['provider'];
  model: AmazonLLMModelValueName;
  config: Partial<AmazonBedrockModelInfo['config']>;
};

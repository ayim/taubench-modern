import { LLMConfiguration, TestLLMConfigurationResponse } from './types';

import { testOpenAiConfiguration } from './openAI';
import { testAzureConfiguration } from './azure';
import { testAmazonConfiguration } from './amazon';

export { LLMConfiguration } from './types';

export const testLLMConfiguration = async (
  configuration: LLMConfiguration,
): Promise<TestLLMConfigurationResponse> => {
  const { provider } = configuration;
  switch (provider) {
    case 'Azure':
      return testAzureConfiguration(configuration);
    case 'OpenAI':
      return testOpenAiConfiguration(configuration);
    case 'Amazon':
      return testAmazonConfiguration(configuration);
    default:
      throw new Error(`Unsupported LLM provider: ${provider}`);
  }
};

import { components } from '@sema4ai/agent-server-interface';
import { Typography, Box } from '@sema4ai/components';
import { IconAzure, IconBedrock, IconOpenAI } from '@sema4ai/icons/logos';
import React from 'react';

type AllPlatformParameters =
  | components['schemas']['OpenAIPlatformParameters']
  | components['schemas']['AzureOpenAIPlatformParameters']
  | components['schemas']['BedrockPlatformParameters'];

export type Provider = Extract<AllPlatformParameters['kind'], 'openai' | 'azure' | 'bedrock'>;

const getProviderIcon = (provider: Provider): React.ReactNode | null => {
  switch (provider) {
    case 'openai':
      return <IconOpenAI />;
    case 'azure':
      return <IconAzure />;
    case 'bedrock':
      return <IconBedrock />;
    default:
      provider satisfies never;
      return null;
  }
};

const getModelName = (model: string) => {
  return model
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const LLMSection = ({ provider, name }: { provider: string; name: string }) => {
  const providerIcon = getProviderIcon(provider.toLowerCase() as Provider);
  return (
    <Box display="flex" flexDirection="column" gap="$10">
      <Typography variant="body-medium" fontWeight="bold">
        LLM
      </Typography>
      <Box display="flex" gap="$4">
        {providerIcon}
        <Typography variant="body-medium">
          {provider} ({getModelName(name)})
        </Typography>
      </Box>
    </Box>
  );
};

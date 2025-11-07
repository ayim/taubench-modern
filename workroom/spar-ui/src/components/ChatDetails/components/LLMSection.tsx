import { Typography, Box } from '@sema4ai/components';
import { getLLMProviderIcon, LLMProvider } from '../../../common/helpers';

const getModelName = (model: string) => {
  return model
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const LLMSection = ({ provider, name }: { provider: string; name: string }) => {
  const ProviderIcon = getLLMProviderIcon(provider.toLowerCase() as LLMProvider);
  return (
    <Box display="flex" flexDirection="column" gap="$10">
      <Typography variant="body-medium" fontWeight="bold">
        LLM
      </Typography>
      <Box display="flex" gap="$4">
        {ProviderIcon && <ProviderIcon />}
        <Typography variant="body-medium">
          {provider} ({getModelName(name)})
        </Typography>
      </Box>
    </Box>
  );
};

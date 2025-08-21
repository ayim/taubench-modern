import { FC, useEffect, useState } from 'react';
import { Box, Input, Select } from '@sema4ai/components';
import { useFormContext, Controller } from 'react-hook-form';

import { AgentDeploymentFormSchema } from './context';
import { mockLLMProviders } from './agent-deployment';

type Props = {
  errorMessage?: string;
};

// Debounce hook
const useDebounce = <T,>(value: T, delay: number) => {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

export const WizardStep2: FC<Props> = ({ errorMessage }) => {
  const { register, watch, control, setValue } = useFormContext<AgentDeploymentFormSchema>();
  const { llmId, apiKey } = watch();

  // Only debounce API key for logging purposes - remove excessive logging
  const debouncedApiKey = useDebounce(apiKey, 500);

  // Log API key changes with debouncing (only for development)
  useEffect(() => {
    if (debouncedApiKey !== undefined && process.env.NODE_ENV === 'development') {
      const selectedLLM = mockLLMProviders.find((llm) => llm.value === llmId);
      const provider = selectedLLM?.provider || 'LLM';
      console.log(`${provider} API key updated`);
    }
  }, [debouncedApiKey, llmId]);

  // Get selected LLM details
  const selectedLLM = mockLLMProviders.find((llm) => llm.value === llmId);

  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <Box>
        <Input label="Name" {...register('name')} error={errorMessage} />
      </Box>

      <Box>
        <Input
          label="Description"
          {...register('description')}
          description="This description is visible to all users who have access to the agent."
          autoGrow={4}
        />
      </Box>

      <Box>
        <Controller
          name="llmId"
          control={control}
          render={({ field }) => (
            <Select
              label="Large Language Model"
              items={mockLLMProviders.map((llm) => ({
                value: llm.value,
                label: llm.label,
                description: `Provider: ${llm.provider}`,
              }))}
              value={field.value}
              onChange={(value) => {
                field.onChange(value);
                // Clear API key when changing LLM provider
                setValue('apiKey', '');
              }}
              description="Select your preferred LLM provider"
            />
          )}
        />
      </Box>

      {selectedLLM && (
        <Box>
          <Input
            label={`${selectedLLM.provider} API Key`}
            {...register('apiKey')}
            type="password"
            placeholder={`Enter your ${selectedLLM.provider} API key`}
            description="Bring your own API key for this LLM provider"
          />
        </Box>
      )}
    </Box>
  );
};

/* eslint-disable camelcase */
import { useEffect, useMemo } from 'react';

import { Link } from '~/components/link/Link';
import { SelectControlled } from '~/components/form/SelectControlled';
import { usePlatformsQuery } from '~/queries/llms';
import { useFormContext } from 'react-hook-form';
import { CreateAgentFormSchema } from './context';

export const LLM = () => {
  const { data: configuredLLMModels, isLoading } = usePlatformsQuery({});
  const { watch, setValue } = useFormContext<CreateAgentFormSchema>();
  const { llmId } = watch();

  useEffect(() => {
    if (!llmId && configuredLLMModels && configuredLLMModels?.length > 0) {
      setValue('llmId', configuredLLMModels[0].platform_id);
    }
  }, [llmId, configuredLLMModels]);

  const providerItems = useMemo(() => {
    const llmOptions = (configuredLLMModels ?? []).map(({ name, kind, platform_id, models }) => {
      const modelsFromPlatform = models ?? {};
      const configuredModel = Object.values(modelsFromPlatform).join(',');

      return {
        optgroup: kind,
        value: platform_id,
        label: `${name} (${configuredModel})`,
      };
    });

    return llmOptions;
  }, [configuredLLMModels]);

  return (
    <SelectControlled
      disabled={isLoading}
      name="llmId"
      items={providerItems}
      label="Large Language Model"
      description={
        <>
          Select the LLM for the Agent, or <Link to="/tenants/$tenantId/configuration/llm/new">Create New</Link>.
        </>
      }
    />
  );
};

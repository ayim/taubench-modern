/* eslint-disable jsx-a11y/anchor-is-valid */
/* eslint-disable camelcase */
import { useMemo } from 'react';
import { AgentDeploymentFormSection } from '../context';

import { Link } from '../../../common/link/Link';
import { SelectControlled } from '../../../common/form/SelectControlled';
import { usePlatformsQuery } from '../../../queries';

// TODO: Update to use the new LLM dialogs once the schema form is merged

export const LLM: AgentDeploymentFormSection = ({ agentTemplate }) => {
  const { data: configuredLLMModels, isLoading } = usePlatformsQuery({});

  const providerItems = useMemo(() => {
    const provider = agentTemplate.model?.provider ?? '';
    const modelName = agentTemplate.model?.name ?? '';
    const recommendedModel = `${provider.toLowerCase()}${modelName}`;

    const llmOptions = (configuredLLMModels ?? []).map(({ name, kind, platform_id, models }) => {
      const modelsFromPlatform = models ?? {};

      const flattenedModelsForConfiguredPlatform = Object.entries(modelsFromPlatform).flatMap(
        ([modelProvider, modelsValues]) => modelsValues.map((model) => `${modelProvider.toLowerCase()}${model}`),
      );

      const configuredModel = Object.values(modelsFromPlatform).join(',');

      return {
        optgroup: kind,
        value: platform_id,
        label: `${name} (${configuredModel})`,
        badge: flattenedModelsForConfiguredPlatform.includes(recommendedModel)
          ? ({ variant: 'success', label: 'Recommended' } as const)
          : undefined,
      };
    });

    return llmOptions;
  }, [configuredLLMModels, agentTemplate]);

  return (
    <SelectControlled
      disabled={isLoading}
      name="llmId"
      items={providerItems}
      label="Large Language Model"
      description={
        <>
          Select the model used by this agent. The recommended option reflects the model configured in the agent
          package, or you can. <Link to="/configuration/llm/new">Create New</Link>.
        </>
      }
    />
  );
};

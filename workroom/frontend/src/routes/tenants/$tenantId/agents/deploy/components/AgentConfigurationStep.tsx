import { Box, Button, Input, Select, SelectItem } from '@sema4ai/components';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams, useRouteContext } from '@tanstack/react-router';
import { FC, useMemo } from 'react';
import { Controller, useFormContext } from 'react-hook-form';

import { AgentDeploymentFormSchema } from './context';
import { AgentPackageResponse } from './AgentUploadForm';

type PlatformConfig = {
  platform_id: string;
  name: string;
  kind: string;
  models?: Record<string, string[]>;
};

type Props = {
  agentTemplate: AgentPackageResponse['agentTemplate'];
};

export const AgentConfigurationStep: FC<Props> = ({ agentTemplate }) => {
  const navigate = useNavigate();
  const {
    register,
    control,
    formState: { errors },
  } = useFormContext<AgentDeploymentFormSchema>();
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/deploy' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  const { data: configuredLLMModels, error: platformsError } = useQuery({
    queryKey: ['platforms', tenantId],
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/');

      if (!response.success) {
        throw new Error(response?.message || 'Failed to fetch platforms');
      }

      return response.data as PlatformConfig[];
    },
  });

  const providerItems = useMemo(() => {
    const recommendedModel = `${agentTemplate.model.provider.toLowerCase()}${agentTemplate.model.name}`;
    const llmOptions = (configuredLLMModels ?? []).map(({ name, kind, platform_id, models }) => {
      const modelsFromPlatform = models ?? {};
      const flattenedModelsForConfiguredPlatform = Object.entries(modelsFromPlatform).flatMap(
        ([modelProvider, models]) => models.map((model) => `${modelProvider.toLocaleLowerCase()}${model}`),
      );

      const configuredModel = Object.values(modelsFromPlatform).join(',');

      return {
        optgroup: kind,
        value: platform_id,
        label: `${name} (${configuredModel})`,
        badge: flattenedModelsForConfiguredPlatform.includes(recommendedModel)
          ? ({ variant: 'success', label: 'Recommended' } as const)
          : undefined,
      } satisfies SelectItem;
    });
    // Fixing react rendering  anv avoid duplicated options
    llmOptions.sort((a, b) => (a.optgroup || '').localeCompare(b.optgroup || '') || a.label.localeCompare(b.label));
    return llmOptions;
  }, [configuredLLMModels, agentTemplate]);

  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <Box>
        {(() => {
          const nameReg = register('name');
          return (
            <Input
              label="Name"
              onChange={(e) => {
                nameReg.onChange(e);
              }}
              onBlur={nameReg.onBlur}
              ref={nameReg.ref}
              name={nameReg.name}
              error={errors.name?.message}
            />
          );
        })()}
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
          render={({ field }) => {
            return (
              <Select
                label="Large Language Model"
                items={providerItems}
                {...field}
                error={errors.llmId?.message ?? ''}
                description="Choose a model platform (e.g., openai, google, anthropic)."
                disabled={providerItems.length === 0}
              />
            );
          }}
        />
        <Box mt="$8">
          <Button onClick={() => navigate({ to: '/tenants/$tenantId/agents/deploy/llms/new', params: { tenantId } })}>
            Configure new LLM
          </Button>
        </Box>
        {platformsError && (
          <Box mt="$8" color="content.error" fontSize="$12">
            {(platformsError as Error).message || 'Failed to load platforms'}
          </Box>
        )}
      </Box>
    </Box>
  );
};

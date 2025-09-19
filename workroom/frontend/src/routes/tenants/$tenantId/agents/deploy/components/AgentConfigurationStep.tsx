import { Box, Button, Input, Select, Typography } from '@sema4ai/components';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams, useRouteContext } from '@tanstack/react-router';
import { FC, useMemo } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { getListPlatformsQueryOptions } from '~/queries/platforms';
import { AgentPackageResponse } from '../../../home/components/AgentUploadForm';
import { AgentDeploymentFormSchema } from './context';
import { IconActions } from '@sema4ai/icons';
import { AgentIcon } from '@sema4ai/layouts';

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

  const { data: configuredLLMModels, error: platformsError } = useQuery(
    getListPlatformsQueryOptions({ tenantId, agentAPIClient }),
  );

  const providerItems = useMemo(() => {
    const recommendedModel = `${agentTemplate.model.provider.toLowerCase()}${agentTemplate.model.name}`;
    const llmOptions = (configuredLLMModels ?? []).map(({ name, kind, platform_id, models }) => {
      const modelsFromPlatform = models ?? {};
      const flattenedModelsForConfiguredPlatform = Object.entries(modelsFromPlatform).flatMap(
        ([modelProvider, models]) => models.map((model) => `${modelProvider.toLowerCase()}${model}`),
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

  const Icon = agentTemplate.icon;

  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <Box>
        <Typography variant="body-medium" mb="$8" fontWeight={500}>
          Icon & Name
        </Typography>
        <Box display="flex" gap="$8">
          {Icon ? <AgentIcon icon={Icon} /> : <AgentIcon icon={IconActions} />}
          <Box width="100%">
            <Input label="" {...register('name')} error={errors.name?.message} />
          </Box>
        </Box>
      </Box>

      <Box>
        <Input
          label="Description"
          {...register('description')}
          description="This description is visible to all users who have access to the agent."
          rows={4}
          error={errors.description?.message}
        />
      </Box>

      <Box>
        <Controller
          name="llmId"
          control={control}
          render={({ field }) => (
            <Select
              label="Large Language Model"
              items={providerItems}
              {...field}
              error={errors.llmId?.message ?? ''}
              description={
                <span>
                  Choose a model platform (e.g., openai, google, anthropic).
                  <Button
                    variant="link"
                    onClick={() => navigate({ to: '/tenants/$tenantId/agents/deploy/llms/new', params: { tenantId } })}
                  >
                    Create New
                  </Button>
                </span>
              }
              disabled={providerItems.length === 0}
            />
          )}
        />
        {platformsError && (
          <Box mt="$8" color="content.error" fontSize="$12">
            {platformsError.message}
          </Box>
        )}
      </Box>
    </Box>
  );
};

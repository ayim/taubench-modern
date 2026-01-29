/* eslint-disable camelcase */
import { useMemo } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Form, Box, Input, Button, useSnackbar } from '@sema4ai/components';
import { FormProvider, useForm } from 'react-hook-form';

import { getGetConfigQueryOptions, useUpdateConfigMutation } from '~/queries/settings';
import { notNil } from '@sema4ai/shared-utils';
import { AgentServerConfigType } from '~/lib/AgentAPIClient';
import { usePlatformsQuery } from '~/queries/platforms';
import { getAllowedModelFromPlatform } from '~/lib/utils';
import { SelectControlled } from '~/components/form/SelectControlled';

const beautifyConfigType = (key: string): string => {
  switch (key) {
    case 'MAX_MCP_SERVERS_IN_AGENT':
      return 'Max MCP servers in Agent';
    default:
      return key
        .toLowerCase()
        .split('_')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
  }
};

export const Route = createFileRoute('/tenants/$tenantId/configuration/settings/')({
  loader: async ({ context: { queryClient, agentAPIClient } }) => {
    const config = await queryClient.ensureQueryData(
      getGetConfigQueryOptions({
        agentAPIClient,
      }),
    );

    if (!config.success) {
      throw new Error(config.message);
    }

    return { config: config.data };
  },
  component: Settings,
});

function Settings() {
  const { tenantId } = Route.useParams();
  const { config } = Route.useLoaderData();
  const formProps = useForm<Record<AgentServerConfigType, string>>({
    defaultValues: Object.fromEntries(config.map(({ config_type, config_value }) => [config_type, config_value])),
  });
  const { addSnackbar } = useSnackbar();

  const { data: platforms, isLoading: isLoadingPlatforms, error: platformsError } = usePlatformsQuery({});

  const evalModelItems = useMemo((): Array<{ value: string; label: string; optgroup?: string }> => {
    const configuredPlatforms = (platforms ?? []).map((platform) => ({
      value: platform.platform_id,
      label: `${platform.name} (${getAllowedModelFromPlatform(platform)})`,
      optgroup: platform.kind,
    }));

    return [{ value: '', label: 'No default model' }, ...configuredPlatforms];
  }, [platforms]);

  const { mutateAsync: updateConfig, isPending: isUpdatingConfig } = useUpdateConfigMutation();

  const onSubmit = formProps.handleSubmit(async (data) => {
    const transformedConfig = (Object.entries(data) as [AgentServerConfigType, string][])
      .map(([config_type, current_value]) => {
        const { isDirty } = formProps.getFieldState(config_type);

        if (!isDirty) {
          return null;
        }

        return {
          config_type,
          current_value,
        };
      })
      .filter(notNil);

    await updateConfig(
      { config: transformedConfig, tenantId },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Settings successfully updated!',
            variant: 'success',
          });
        },
        onError: (error) => {
          addSnackbar({
            message: error.message || 'Failed to update settings',
            variant: 'danger',
          });
        },
      },
    );
  });

  return (
    <Form onSubmit={onSubmit} busy={isUpdatingConfig}>
      <FormProvider {...formProps}>
        {config.map((configEntry) => (
          <Form.Fieldset key={configEntry.config_type}>
            {configEntry.config_type === 'GLOBAL_EVAL_PLATFORM_PARAMS_ID' ? (
              <SelectControlled
                name={configEntry.config_type}
                label={beautifyConfigType(configEntry.config_type)}
                description={
                  platformsError ? 'Failed to load available models. Please try again.' : configEntry.description
                }
                items={evalModelItems}
                disabled={isLoadingPlatforms}
                error={formProps.formState.errors[configEntry.config_type]?.message ?? ''}
                placeholder="Select a model"
              />
            ) : (
              <Input
                label={beautifyConfigType(configEntry.config_type)}
                description={configEntry.description}
                {...formProps.register(configEntry.config_type)}
              />
            )}
          </Form.Fieldset>
        ))}
        <Box display="flex" justifyContent="flex-end">
          <Button type="submit" variant="primary" loading={isUpdatingConfig} round>
            Submit
          </Button>
        </Box>
      </FormProvider>
    </Form>
  );
}

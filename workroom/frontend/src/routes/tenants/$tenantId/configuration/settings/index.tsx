import { createFileRoute, useRouteContext } from '@tanstack/react-router';
import { Form, Box, Input, Button, Select, useSnackbar } from '@sema4ai/components';
import { FormProvider, useForm, Controller } from 'react-hook-form';
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { getGetConfigQueryOptions, useUpdateConfigMutation } from '~/queries/settings';
import { notNil } from '@sema4ai/shared-utils';
import { AgentServerConfigType } from '~/lib/AgentAPIClient';
import { getListPlatformsQueryOptions } from '~/queries/platforms';
import { getAllowedModelFromPlatform } from '~/lib/utils';

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
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const config = await queryClient.ensureQueryData(
      getGetConfigQueryOptions({
        agentAPIClient,
        tenantId,
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
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const formProps = useForm<Record<AgentServerConfigType, string>>({
    defaultValues: Object.fromEntries(config.map(({ config_type, config_value }) => [config_type, config_value])),
  });
  const { addSnackbar } = useSnackbar();

  const {
    data: platforms,
    isLoading: isLoadingPlatforms,
    error: platformsError,
  } = useQuery(getListPlatformsQueryOptions({ agentAPIClient, tenantId }));

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
              <Controller
                control={formProps.control}
                name={configEntry.config_type}
                render={({ field }) => (
                  <Select
                    label={beautifyConfigType(configEntry.config_type)}
                    description={
                      platformsError ? 'Failed to load available models. Please try again.' : configEntry.description
                    }
                    placeholder="Select a model"
                    items={evalModelItems}
                    disabled={isLoadingPlatforms}
                    error={formProps.formState.errors[configEntry.config_type]?.message ?? ''}
                    {...field}
                  />
                )}
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

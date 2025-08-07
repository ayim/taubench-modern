import { createFileRoute } from '@tanstack/react-router';
import { Form, Box, Header, Scroll, Input, Button } from '@sema4ai/components';
import { FormProvider, useForm } from 'react-hook-form';

import { getGetConfigQueryOptions, useUpdateConfigMutation } from '~/queries/settings';
import { notNil } from '@sema4ai/robocloud-shared-utils';
import { successToast } from '~/utils/toasts';

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

export const Route = createFileRoute('/$tenantId/settings/')({
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const config = await queryClient.ensureQueryData(
      getGetConfigQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    );
    return { config, tenantId };
  },
  component: Settings,
});

function Settings() {
  const { config, tenantId } = Route.useLoaderData();
  const formProps = useForm<Record<string, string>>({
    defaultValues: Object.fromEntries(config.map(({ config_type, config_value }) => [config_type, config_value])),
  });

  const { mutateAsync: updateConfig, isPending: isUpdatingConfig } = useUpdateConfigMutation();

  const onSubmit = formProps.handleSubmit(async (data) => {
    const transformedConfig = Object.entries(data)
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
          // API calls may not be issued if there are no settings to update
          // Yet we "toast success" for better UX

          successToast(`Settings successfully updated!`);
        },
        onError: () => {},
      },
    );
  });

  return (
    <Scroll>
      <Box p="$24" pb="$48">
        <Header size="x-large">
          <Header.Title title="Settings" />
        </Header>

        <Form onSubmit={onSubmit} width={720} busy={isUpdatingConfig}>
          <FormProvider {...formProps}>
            {config.map((configEntry) => (
              <Form.Fieldset key={configEntry.config_type}>
                <Input
                  label={beautifyConfigType(configEntry.config_type)}
                  {...formProps.register(configEntry.config_type)}
                />
              </Form.Fieldset>
            ))}
            <Box>
              <Button type="submit" variant="primary" loading={isUpdatingConfig} round>
                Submit
              </Button>
            </Box>
          </FormProvider>
        </Form>
      </Box>
    </Scroll>
  );
}

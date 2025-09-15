import { zodResolver } from '@hookform/resolvers/zod';
import { Form, Box, Button, EmptyState, Scroll, Input, useSnackbar } from '@sema4ai/components';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createFileRoute, Link, useRouteContext } from '@tanstack/react-router';
import { useCallback } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import z from 'zod';

import errorIllustration from '~/assets/error.svg';
import { useTenantContext } from '~/lib/tenantContext';
import {
  getGetDocumentIntelligenceQueryKey,
  getGetDocumentIntelligenceQueryOptions,
  useClearDocumentIntelligenceConfigMutation,
  useUpsertDocumentIntelligenceConfigMutation,
} from '~/queries/documentIntelligence';

const SEMA4_HOSTED_REDUCTO_ENDPOINT = 'https://backend.sema4.ai/reducto';

type Configuration = z.infer<typeof Configuration>;
const Configuration = z.object({
  reductoEndpoint: z.string().min(1),
  reductoApiKey: z.string().min(1, 'The API key must be specified'),
  postgresConnectionUrl: z
    .string()
    .regex(
      /^(postgres(ql)?):\/\/([^:]+)(:([^@]+))?@([^:/]+)(:\d+)?\/([^\s?]+)(\?.*)?$/,
      'Invalid connection string: expecting the following shape postgresql://user:password@host:port/database?sslmode=require',
    ),
});

export const Route = createFileRoute('/tenants/$tenantId/configuration/documentIntelligence/')({
  component: View,
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const documentIntelligence = await queryClient.ensureQueryData(
      getGetDocumentIntelligenceQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    );
    return { documentIntelligence };
  },
});

function View() {
  const queryClient = useQueryClient();
  const { tenantId } = Route.useParams();
  const { addSnackbar } = useSnackbar();
  const { documentIntelligence: documentIntelligenceFromRoute } = Route.useLoaderData();
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const documentIntelligence = useQuery({
    ...getGetDocumentIntelligenceQueryOptions({
      agentAPIClient,
      tenantId,
    }),
    initialData: documentIntelligenceFromRoute,
  });

  const { features } = useTenantContext();
  const formProps = useForm<Configuration>({
    defaultValues: {
      reductoEndpoint: SEMA4_HOSTED_REDUCTO_ENDPOINT,
      reductoApiKey: '',
      postgresConnectionUrl: '',
    },
    resolver: zodResolver(Configuration),
  });

  const { mutateAsync: upsertDocumentIntelligenceConfiguration, isPending: isUpdatingConfig } =
    useUpsertDocumentIntelligenceConfigMutation();

  const { mutateAsync: clearDocumentIntelligenceConfiguration, isPending: isClearingConfig } =
    useClearDocumentIntelligenceConfigMutation();

  const onSubmit = formProps.handleSubmit(async (configuration) => {
    await upsertDocumentIntelligenceConfiguration(
      { tenantId, configuration },
      {
        onSuccess: async () => {
          addSnackbar({
            message: 'Document Intelligence successfully configured!',
            variant: 'success',
          });
          queryClient.invalidateQueries({ queryKey: getGetDocumentIntelligenceQueryKey(tenantId) });
        },
        onError: (error) => {
          addSnackbar({
            message: error.message,
            variant: 'danger',
          });
        },
      },
    );
  });

  const handleClearConfig = useCallback(async () => {
    await clearDocumentIntelligenceConfiguration(
      { tenantId },
      {
        onSuccess: async () => {
          addSnackbar({
            message: 'Document Intelligence successfully cleared!',
            variant: 'success',
          });
          queryClient.invalidateQueries({ queryKey: getGetDocumentIntelligenceQueryKey(tenantId) });
        },
        onError: (error) => {
          addSnackbar({
            message: error.message,
            variant: 'danger',
          });
        },
      },
    );
  }, [tenantId, queryClient, clearDocumentIntelligenceConfiguration, addSnackbar]);

  if (!features.documentIntelligence.enabled) {
    return (
      <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="calc(100% - 72px)">
        <EmptyState
          illustration={<img src={errorIllustration} loading="lazy" alt="" />}
          title="Page not available"
          description="Document Intelligence is not enabled for your Workspace"
          action={
            <Link to="/tenants/$tenantId/home" params={{ tenantId }}>
              <Button forwardedAs="span" round>
                Return to Home
              </Button>
            </Link>
          }
        />
      </Box>
    );
  }

  const isProcessingRequest = isUpdatingConfig || isClearingConfig;

  return (
    <Scroll>
      <Box p={8}>
        <Form onSubmit={onSubmit} busy={isProcessingRequest}>
          <FormProvider {...formProps}>
            <Form.Fieldset key={'reducto_endpoint'}>
              <Input
                label="Reducto Endpoint"
                placeholder="Reducto endpoint"
                {...formProps.register('reductoEndpoint')}
                error={formProps.formState.errors.reductoEndpoint?.message}
              />
            </Form.Fieldset>
            <Form.Fieldset key={'reducto_api_key'}>
              <Input
                label="Reducto API Key"
                placeholder="Your API Key"
                {...formProps.register('reductoApiKey')}
                error={formProps.formState.errors.reductoApiKey?.message}
              />
            </Form.Fieldset>
            <Form.Fieldset key={'postgres_connection_details'}>
              <Input
                label="Bring your Own Database"
                placeholder="PostgreSQL connection string"
                {...formProps.register('postgresConnectionUrl')}
                error={formProps.formState.errors.postgresConnectionUrl?.message}
              />
            </Form.Fieldset>
            <Box display="flex" justifyContent="flex-end">
              <Box pl="$8" display="flex" gap={8}>
                <Button
                  variant="secondary"
                  disabled={!documentIntelligence.data.configured}
                  onClick={handleClearConfig}
                  round
                >
                  Clear
                </Button>
                <Button type="submit" variant="primary" loading={isProcessingRequest} round>
                  {documentIntelligence.data.configured ? 'Update configuration' : 'Configure'}
                </Button>
              </Box>
            </Box>
          </FormProvider>
        </Form>
      </Box>
    </Scroll>
  );
}

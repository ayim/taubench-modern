import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, EmptyState, Form, Input, Select, useSnackbar } from '@sema4ai/components';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { Controller, FormProvider, useForm } from 'react-hook-form';
import z from 'zod';

import { useDataConnectionsQuery } from '~/queries/dataConnections';
import errorIllustration from '~/assets/error.svg';
import { InputControlled } from '~/components/InputControlled';
import { useTenantContext } from '~/lib/tenantContext';
import { getApiKeyValue } from '~/queries/agent-interface-patches';
import {
  useClearDocumentIntelligenceConfigMutation,
  useDocumentIntelligenceQuery,
  useUpsertDocumentIntelligenceConfigMutation,
} from '~/queries/documentIntelligence';

const SEMA4_HOSTED_DOCUMENT_INTELLIGENCE_ENDPOINT = 'https://backend.sema4.ai/reducto';

type Configuration = z.infer<typeof Configuration>;
const Configuration = z.object({
  documentIntelligenceEndpoint: z.string().min(1),
  documentIntelligenceApiKey: z.string().min(1, 'The API key must be specified'),
  dataConnectionId: z.string().uuid('Please select a data connection'),
});

export const Route = createFileRoute('/tenants/$tenantId/configuration/documentIntelligence/')({
  component: View,
});

function View() {
  const navigate = useNavigate();
  const { tenantId } = Route.useParams();
  const { addSnackbar } = useSnackbar();
  const { data: documentIntelligence } = useDocumentIntelligenceQuery({});

  const { features } = useTenantContext();

  const dataConnections = useDataConnectionsQuery({});

  const currentConfig = documentIntelligence?.status === 'configured' ? documentIntelligence?.configuration : null;

  const formProps = useForm<Configuration>({
    defaultValues: {
      documentIntelligenceEndpoint:
        currentConfig?.integrations?.[0]?.endpoint ?? SEMA4_HOSTED_DOCUMENT_INTELLIGENCE_ENDPOINT,
      documentIntelligenceApiKey: getApiKeyValue(currentConfig?.integrations?.[0]?.api_key),
      dataConnectionId: currentConfig?.data_connection_id ?? '',
    },
    resolver: zodResolver(Configuration),
  });

  const isConfigured = (currentConfig?.integrations?.length ?? 0) > 0 && !!currentConfig?.data_connection_id;

  const postgresConnections = (dataConnections.data ?? [])
    .filter((connection) => connection.engine === 'postgres')
    .map((connection) => ({ value: connection.id, label: connection.name }));

  const hasPostgresConnections = postgresConnections.length > 0;

  const { mutateAsync: upsertDocumentIntelligenceConfiguration, isPending: isUpdatingConfig } =
    useUpsertDocumentIntelligenceConfigMutation();

  const { mutateAsync: clearDocumentIntelligenceConfiguration, isPending: isClearingConfig } =
    useClearDocumentIntelligenceConfigMutation();

  const onSubmit = formProps.handleSubmit(async (configuration) => {
    await upsertDocumentIntelligenceConfiguration(
      { tenantId, configuration },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Document Intelligence successfully configured!',
            variant: 'success',
          });
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

  const onClearConfirm = useDeleteConfirm(
    {
      entityType: 'the document intelligence configuration',
    },
    [],
  );

  const handleClearConfig = onClearConfirm(async () => {
    await clearDocumentIntelligenceConfiguration(undefined, {
      onSuccess: () => {
        addSnackbar({
          message: 'Document Intelligence successfully cleared!',
          variant: 'success',
        });
        formProps.reset({
          documentIntelligenceEndpoint: SEMA4_HOSTED_DOCUMENT_INTELLIGENCE_ENDPOINT,
          documentIntelligenceApiKey: '',
          dataConnectionId: '',
        });
      },
      onError: (error) => {
        addSnackbar({
          message: error.message,
          variant: 'danger',
        });
      },
    });
  });

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

  const formKey = isConfigured ? 'configured' : 'not-configured';

  return (
    <Form key={formKey} onSubmit={onSubmit} busy={isProcessingRequest}>
      <FormProvider {...formProps}>
        <Form.Fieldset key={'document_intelligence_endpoint'}>
          <Input
            label="Document Intelligence Endpoint"
            placeholder="Document Intelligence Endpoint"
            {...formProps.register('documentIntelligenceEndpoint')}
            error={formProps.formState.errors.documentIntelligenceEndpoint?.message}
            disabled={isConfigured}
          />
        </Form.Fieldset>
        <Form.Fieldset key={'document_intelligence_api_key'}>
          <InputControlled
            fieldName="documentIntelligenceApiKey"
            type="password"
            label="Document Intelligence API Key"
            placeholder="Your API Key"
            {...formProps.register('documentIntelligenceApiKey')}
            error={formProps.formState.errors.documentIntelligenceApiKey?.message}
          />
        </Form.Fieldset>
        <Form.Fieldset key={'postgres_connection_details'}>
          <Controller
            control={formProps.control}
            name="dataConnectionId"
            render={({ field }) => (
              <Select
                label="Bring your Own Database"
                placeholder="Select a PostgreSQL data connection"
                items={postgresConnections}
                error={formProps.formState.errors.dataConnectionId?.message}
                disabled={isConfigured}
                description={
                  !hasPostgresConnections && !isConfigured ? (
                    <span>
                      No PostgreSQL connections found.{' '}
                      <Button
                        variant="link"
                        onClick={() =>
                          navigate({
                            to: '/tenants/$tenantId/data-access/data-connections/create',
                            params: { tenantId },
                          })
                        }
                      >
                        Create New Data Connection
                      </Button>
                    </span>
                  ) : undefined
                }
                {...field}
              />
            )}
          />
        </Form.Fieldset>
        <Box display="flex" justifyContent="flex-end">
          <Box pl="$8" display="flex" gap={8}>
            <Button variant="secondary" disabled={!isConfigured} onClick={handleClearConfig} round>
              Clear
            </Button>
            {!isConfigured && (
              <Button
                type="submit"
                variant="primary"
                loading={isProcessingRequest}
                disabled={!hasPostgresConnections}
                round
              >
                Create Configuration
              </Button>
            )}
          </Box>
        </Box>
      </FormProvider>
    </Form>
  );
}

import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, EmptyState, Form, Input, useSnackbar } from '@sema4ai/components';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { createFileRoute, Link } from '@tanstack/react-router';
import { useEffect } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import z from 'zod';

import errorIllustration from '~/assets/error.svg';
import { InputControlled } from '~/components/form/InputControlled';
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
});

export const Route = createFileRoute('/tenants/$tenantId/configuration/documentIntelligence/')({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  const { addSnackbar } = useSnackbar();
  const { data: documentIntelligence, isLoading } = useDocumentIntelligenceQuery({});

  const { features } = useTenantContext();

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

  if (isLoading) {
    return null;
  }

  return (
    <DocumentIntelligenceForm
      tenantId={tenantId}
      documentIntelligence={documentIntelligence}
      addSnackbar={addSnackbar}
    />
  );
}

function DocumentIntelligenceForm({
  tenantId,
  documentIntelligence,
  addSnackbar,
}: {
  tenantId: string;
  documentIntelligence: ReturnType<typeof useDocumentIntelligenceQuery>['data'];
  addSnackbar: ReturnType<typeof useSnackbar>['addSnackbar'];
}) {
  const currentConfig = documentIntelligence?.status === 'configured' ? documentIntelligence?.configuration : null;

  const formProps = useForm<Configuration>({
    defaultValues: {
      documentIntelligenceEndpoint:
        currentConfig?.integrations?.[0]?.endpoint ?? SEMA4_HOSTED_DOCUMENT_INTELLIGENCE_ENDPOINT,
      documentIntelligenceApiKey: getApiKeyValue(currentConfig?.integrations?.[0]?.api_key),
    },
    resolver: zodResolver(Configuration),
  });

  useEffect(() => {
    formProps.reset({
      documentIntelligenceEndpoint:
        currentConfig?.integrations?.[0]?.endpoint ?? SEMA4_HOSTED_DOCUMENT_INTELLIGENCE_ENDPOINT,
      documentIntelligenceApiKey: getApiKeyValue(currentConfig?.integrations?.[0]?.api_key),
    });
  }, [currentConfig]);

  const isConfigured = (currentConfig?.integrations?.length ?? 0) > 0;

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

  const isProcessingRequest = isUpdatingConfig || isClearingConfig;

  return (
    <Form onSubmit={onSubmit} busy={isProcessingRequest}>
      <FormProvider {...formProps}>
        <Form.Fieldset key="document_intelligence_endpoint">
          <Input
            label="Document Intelligence Endpoint"
            placeholder="Document Intelligence Endpoint"
            {...formProps.register('documentIntelligenceEndpoint')}
            error={formProps.formState.errors.documentIntelligenceEndpoint?.message}
            disabled={isConfigured}
          />
        </Form.Fieldset>
        <Form.Fieldset key="document_intelligence_api_key">
          <InputControlled
            fieldName="documentIntelligenceApiKey"
            type="password"
            label="Document Intelligence API Key"
            placeholder="Your API Key"
            error={formProps.formState.errors.documentIntelligenceApiKey?.message}
          />
        </Form.Fieldset>
        <Box display="flex" justifyContent="flex-end">
          <Box pl="$8" display="flex" gap={8}>
            <Button variant="secondary" disabled={!isConfigured} onClick={handleClearConfig} round>
              Clear
            </Button>
            <Button type="submit" variant="primary" loading={isProcessingRequest} round>
              {isConfigured ? 'Save' : 'Create Configuration'}
            </Button>
          </Box>
        </Box>
      </FormProvider>
    </Form>
  );
}

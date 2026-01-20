import { FC, useEffect, useMemo } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Form, Progress, Tooltip, useSnackbar } from '@sema4ai/components';

import {
  useObservabilityIntegrationQuery,
  useUpdateObservabilityIntegrationMutation,
  useValidateObservabilityIntegrationMutation,
} from '../../../queries';
import { ObservabilitySettingsForm } from './ObservabilitySettingsForm';
import {
  apiResponseToFormValues,
  ObservabilitySettingsFormSchema,
  observabilitySettingsSchema,
  toObservabilitySettings,
} from './observabilitySettingsSchema';

type Props = {
  integrationId: string;
};

export const UpdateObservabilityIntegration: FC<Props> = ({ integrationId }) => {
  const { addSnackbar } = useSnackbar();
  const { mutateAsync: updateObservabilityIntegration, isPending } = useUpdateObservabilityIntegrationMutation({
    integrationId,
  });
  const { mutateAsync: validateObservabilityIntegration, isPending: isValidating } =
    useValidateObservabilityIntegrationMutation({
      integrationId,
    });
  const { data: observabilityIntegration, isFetching } = useObservabilityIntegrationQuery({ integrationId });

  const formMethods = useForm<ObservabilitySettingsFormSchema>({
    resolver: zodResolver(observabilitySettingsSchema),
    defaultValues: {},
    mode: 'onChange',
  });

  const {
    handleSubmit,
    reset,
    watch,
    formState: { isValid, isDirty },
  } = formMethods;

  const isEnabled = watch('is_enabled');
  const currentProvider = watch('provider');

  const defaultValues = useMemo(
    () => (observabilityIntegration?.settings ? apiResponseToFormValues(observabilityIntegration.settings) : undefined),
    [observabilityIntegration],
  );

  useEffect(() => {
    if (defaultValues) {
      reset(defaultValues);
    }
  }, [defaultValues, reset]);

  const onSubmit = handleSubmit((data) => {
    const payload = toObservabilitySettings(data);

    updateObservabilityIntegration(payload, {
      onSuccess: () => {
        addSnackbar({ message: 'Observability settings saved successfully', variant: 'success' });
      },
      onError: (error) => {
        addSnackbar({
          message: error.message,
          variant: 'danger',
        });
      },
    });
  });

  const onTest = async () => {
    await validateObservabilityIntegration(
      {},
      {
        onSuccess: (result) => {
          if (result.success) {
            addSnackbar({
              message: result.message || 'Test successful! Heartbeat sent to observability platform.',
              variant: 'success',
            });
          } else {
            addSnackbar({
              message: result.message || 'Test failed',
              variant: 'danger',
            });
          }
        },
        onError: (error) => {
          addSnackbar({
            message: error.message || 'Failed to test observability integration',
            variant: 'danger',
          });
        },
      },
    );
  };

  if (isFetching) {
    return <Progress variant="default" />;
  }

  const savedProvider = observabilityIntegration?.settings.provider;
  const isProviderMismatch = currentProvider !== savedProvider;
  const isValidationDisabled = isValidating || isPending || isDirty || !isEnabled || isProviderMismatch;
  const isUpdatingDisabled = isPending || !isValid || isValidating;

  const validationTooltipText: string | null = (() => {
    if (!isEnabled) {
      return 'Enable observability to test the configuration.';
    }
    if (isDirty || isProviderMismatch) {
      return 'Update the configuration first to be able to test it.';
    }
    return null;
  })();

  return (
    <Form onSubmit={onSubmit}>
      <FormProvider {...formMethods}>
        <ObservabilitySettingsForm defaultValues={defaultValues} />

        <Box display="flex" alignItems="center" justifyContent="end" gap="$8">
          <Tooltip text={validationTooltipText}>
            <Button
              type="button"
              variant="secondary"
              loading={isValidating}
              disabled={isValidationDisabled}
              round
              onClick={onTest}
            >
              Test
            </Button>
          </Tooltip>
          <Button type="submit" loading={isPending} disabled={isUpdatingDisabled} round>
            Update
          </Button>
        </Box>
      </FormProvider>
    </Form>
  );
};

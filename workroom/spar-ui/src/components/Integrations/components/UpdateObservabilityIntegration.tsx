import { FC, useEffect, useMemo } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Form, Progress, useSnackbar } from '@sema4ai/components';

import { useObservabilityIntegrationQuery, useUpdateObservabilityIntegrationMutation } from '../../../queries';
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
  const { data: observabilityIntegration, isFetching } = useObservabilityIntegrationQuery({ integrationId });

  const formMethods = useForm<ObservabilitySettingsFormSchema>({
    resolver: zodResolver(observabilitySettingsSchema),
    defaultValues: {},
    mode: 'onChange',
  });

  const {
    handleSubmit,
    reset,
    formState: { isValid },
  } = formMethods;

  const defaultValues = useMemo(
    () => (observabilityIntegration?.settings ? apiResponseToFormValues(observabilityIntegration.settings) : undefined),
    [observabilityIntegration],
  );

  useEffect(() => {
    if (defaultValues) {
      reset(defaultValues);
    }
  }, [defaultValues]);

  const onSubmit = handleSubmit((data) => {
    /**
     * @TODO:
     * Add configuration validation when Agent Server endpoint is ready.
     */
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

  if (isFetching) {
    return <Progress variant="default" />;
  }

  return (
    <Form onSubmit={onSubmit}>
      <FormProvider {...formMethods}>
        <ObservabilitySettingsForm defaultValues={defaultValues} />

        <Box display="flex" alignItems="center" justifyContent="end">
          <Button type="submit" loading={isPending} disabled={isPending || !isValid} round>
            Update
          </Button>
        </Box>
      </FormProvider>
    </Form>
  );
};

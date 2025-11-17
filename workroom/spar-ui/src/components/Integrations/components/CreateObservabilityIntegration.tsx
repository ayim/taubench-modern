import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { Box, Button, Form, useSnackbar } from '@sema4ai/components';
import { useCreateObservabilityIntegrationMutation } from '../../../queries';
import { ObservabilitySettingsForm } from './ObservabilitySettingsForm';
import {
  ObservabilitySettingsFormSchema,
  observabilitySettingsSchema,
  toObservabilitySettings,
} from './observabilitySettingsSchema';

export const CreateObservabilityIntegration = () => {
  const { addSnackbar } = useSnackbar();
  const { mutateAsync: createObservabilityIntegration, isPending } = useCreateObservabilityIntegrationMutation({});

  const formMethods = useForm<ObservabilitySettingsFormSchema>({
    resolver: zodResolver(observabilitySettingsSchema),
    defaultValues: {},
    mode: 'onChange',
  });

  const {
    handleSubmit,
    formState: { isValid },
  } = formMethods;

  const onSubmit = handleSubmit((data) => {
    /**
     * @TODO:
     * Add configuration validation when Agent Server endpoint is ready.
     */
    const payload = toObservabilitySettings(data);

    createObservabilityIntegration(payload, {
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

  return (
    <Form onSubmit={onSubmit}>
      <FormProvider {...formMethods}>
        <ObservabilitySettingsForm />

        <Box display="flex" alignItems="center" justifyContent="end">
          <Button type="submit" loading={isPending} disabled={isPending || !isValid} round>
            Save
          </Button>
        </Box>
      </FormProvider>
    </Form>
  );
};

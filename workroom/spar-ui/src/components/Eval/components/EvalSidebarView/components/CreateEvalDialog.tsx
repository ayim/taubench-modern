import { FC, useEffect } from "react";
import z from "zod";
import { Dialog, Box, Typography, Form, Input, Button, Progress, Switch } from "@sema4ai/components";
import { IconChemicalBottle, IconArrowRight } from "@sema4ai/icons";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

const evaluationCriteriaSchema = z.object({
  responseAccuracyExpectation: z
    .string()
    .max(2000, 'Expectation must be less than 2000 characters')
    .default(''),
});

const createEvalFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name must be less than 100 characters'),
  description: z.string().max(500, 'Description must be less than 500 characters').default(''),
  useLiveExecution: z.boolean().default(false),
  evaluationCriteria: evaluationCriteriaSchema,
}).superRefine((value, ctx) => {
  if (value.useLiveExecution && value.evaluationCriteria.responseAccuracyExpectation.trim().length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['evaluationCriteria', 'responseAccuracyExpectation'],
      message: 'Expectation is required when live actions are enabled',
    });
  }
});

export type CreateEvalFormData = z.infer<typeof createEvalFormSchema>;

export interface CreateEvalDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateEvalFormData) => Promise<void>;
  isLoading: boolean;
  initialValues?: Partial<CreateEvalFormData>;
  mode?: 'create' | 'edit';
}

export const CreateEvalDialog: FC<CreateEvalDialogProps> = ({
  open,
  onClose,
  onSubmit,
  isLoading = false,
  initialValues,
  mode = 'create',
}) => {
  const isEditMode = mode === 'edit';
  const form = useForm<CreateEvalFormData>({
    resolver: zodResolver(createEvalFormSchema),
    defaultValues: {
      name: initialValues?.name || '',
      description: initialValues?.description || '',
      useLiveExecution: initialValues?.useLiveExecution ?? false,
      evaluationCriteria: {
        responseAccuracyExpectation:
          initialValues?.evaluationCriteria?.responseAccuracyExpectation ?? '',
      },
    },
    mode: 'onChange',
  });

  const {
    register,
    control,
    watch,
    formState: { errors, isValid },
    handleSubmit,
    reset,
  } = form;

  useEffect(() => {
    register('description');
  }, [register]);

  const liveActionsEnabled = watch('useLiveExecution', false);

  const evaluationSummaryItems = liveActionsEnabled
    ? [
        {
          id: 'response-accuracy-live',
          description: "Response accuracy — compares the agent's answer with your expected outcome.",
        },
      ]
    : [
        {
          id: 'action-calling',
          description:
            'Action calling — exhaustive on actions with strict order and arguments.',
        },
        {
          id: 'flow-adherence',
          description: 'Flow adherence — checks the conversation follows the recorded scenario.',
        },
        {
          id: 'response-accuracy-replay',
          description: 'Response accuracy — scores replies against the expectation you provide.',
        },
      ];

  useEffect(() => {
    if (open && initialValues) {
      reset({
        name: initialValues.name || '',
        description: initialValues.description || '',
        useLiveExecution: initialValues.useLiveExecution ?? false,
        evaluationCriteria: {
          responseAccuracyExpectation:
            initialValues.evaluationCriteria?.responseAccuracyExpectation ?? '',
        },
      });
    }
  }, [open, initialValues, reset]);

  const handleFormSubmit = handleSubmit(async (data) => {
    const description = data.description || initialValues?.description || '';
    await onSubmit({ ...data, description });
    reset({
      name: '',
      description: '',
      useLiveExecution: false,
      evaluationCriteria: {
        responseAccuracyExpectation: '',
      },
    });
  });

  const handleClose = () => {
    reset({
      name: '',
      description: '',
      useLiveExecution: false,
      evaluationCriteria: {
        responseAccuracyExpectation: '',
      },
    });
    onClose();
  };

  if (isLoading) {
    return (
      <Dialog width={800} open={open} onClose={handleClose}>
        <Dialog.Header>
          <Dialog.Header.Title title="" />
        </Dialog.Header>
        
        <Dialog.Content>
          <Box display="flex" flexDirection="column" alignItems="center" gap="$16" padding="$32">
            <Progress size="large" />
            <Typography variant="display-large">
              {isEditMode ? 'Updating Your Evaluation' : 'Creating Your Evaluation'}
            </Typography>
            <Typography variant="body-medium">
              {isEditMode
                ? 'Your changes will be saved in a few seconds.'
                : 'Your Evaluation will be available in a few seconds.'}
            </Typography>
          </Box>
        </Dialog.Content>
        
        <Dialog.Actions>
          <Button 
            variant="secondary" 
            onClick={handleClose}
            disabled
            round
          >
            Cancel
          </Button>
        </Dialog.Actions>
      </Dialog>
    );
  }

  return (
    <Dialog width={800} open={open} onClose={handleClose}>
      <Dialog.Header>
        <Dialog.Header.Title title={
          <Box display="flex" alignItems="center" gap="$8">
            <IconChemicalBottle />
            <Typography variant='display-small'>
              {isEditMode ? 'Edit Evaluation Scenario' : 'Create Evaluation Scenario'}
            </Typography>
          </Box>
        } />
      </Dialog.Header>
      
      <Dialog.Content>
        <Form onSubmit={handleFormSubmit}>
          <Form.Fieldset>
            <Input 
              label="Name" 
              disabled={isLoading}
              error={errors.name?.message}
              {...register('name')} 
            />
            <Controller
              name="useLiveExecution"
              control={control}
              render={({ field: { value, onChange } }) => (
                <Box display="flex" alignItems="center" gap="$8">
                  <Switch
                    aria-labelledby="support-live-actions-label"
                    checked={value}
                    onChange={(event) => onChange(event.target.checked)}
                    disabled={isLoading}
                  />
                  <Box display="flex" flexDirection="column" gap="$2">
                    <Typography id="support-live-actions-label" variant="body-medium">
                      Support live actions
                    </Typography>
                    <Typography variant="body-small" color="content.subtle">
                      Run tool calls live instead of replaying the recorded outputs.
                    </Typography>
                  </Box>
                </Box>
              )}
            />
            <Box display="flex" flexDirection="column" gap="$8">
              <Typography variant="display-small">What is Evaluated</Typography>
              <Box
                display="flex"
                flexDirection="column"
                as="ul"
                gap="$4"
                padding="$0"
                margin="$0"
                style={{ listStyle: 'none' }}
              >
                {evaluationSummaryItems.map((item) => (
                  <Box
                    key={item.id}
                    as="li"
                    display="flex"
                    alignItems="center"
                    gap="$6"
                    padding="$6"
                  >
                    <Box
                      display="flex"
                      alignItems="center"
                      justifyContent="center"
                      width="$16"
                      height="$16"
                      borderRadius="9999px"
                      backgroundColor="content.subtle"
                      flexShrink={0}
                    >
                      <IconArrowRight aria-hidden size={12} color="background.primary" />
                    </Box>
                    <Typography variant="body-small">{item.description}</Typography>
                  </Box>
                ))}
              </Box>
              <Input
                label=""
                description={
                  liveActionsEnabled
                    ? "Add anything else you want us to check."
                    : 'Add anything else you want us to check. Leave blank to skip the response accuracy check.'
                }
                rows={4}
                disabled={isLoading}
                error={errors.evaluationCriteria?.responseAccuracyExpectation?.message}
                {...register('evaluationCriteria.responseAccuracyExpectation')}
              />
            </Box>
          </Form.Fieldset>
        </Form>
      </Dialog.Content>
      
      <Dialog.Actions>
        <Button 
          type="submit" 
          onClick={handleFormSubmit}
          disabled={!isValid || isLoading}
          loading={isLoading}
          round
        >
          {isEditMode ? 'Save changes' : 'Create'}
        </Button>
        <Button 
          variant="secondary" 
          onClick={handleClose}
          disabled={isLoading}
          round
        >
          Cancel
        </Button>
      </Dialog.Actions>
    </Dialog>
  );
};

import { FC, useEffect, useState } from "react";
import z from "zod";
import { Dialog, Box, Typography, Form, Input, Button, Progress, Checkbox } from "@sema4ai/components";
import { IconChemicalBottle } from "@sema4ai/icons";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

const evaluationCriteriaSchema = z
  .object({
    actionCalling: z.boolean().default(true),
    actionCallingPolicy: z
      .object({
        assertAllConsumed: z.boolean().default(true),
        allowLlmArgValidation: z.boolean().default(false),
        allowLlmInterpolation: z.boolean().default(false),
      })
      .default({
        assertAllConsumed: true,
        allowLlmArgValidation: false,
        allowLlmInterpolation: false,
      }),
    flowAdherence: z.boolean().default(true),
    responseAccuracy: z.boolean().default(true),
    responseAccuracyExpectation: z
      .string()
      .max(2000, 'Expectation must be less than 2000 characters')
      .default(''),
  })
  .superRefine((value, ctx) => {
    if (value.responseAccuracy && value.responseAccuracyExpectation.trim().length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['responseAccuracyExpectation'],
        message: 'Expectation is required when response accuracy is selected',
      });
    }
  });

const createEvalFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name must be less than 100 characters'),
  description: z.string().min(1, 'Description is required').max(500, 'Description must be less than 500 characters'),
  useLiveExecution: z.boolean().default(false),
  evaluationCriteria: evaluationCriteriaSchema,
});

export type CreateEvalFormData = z.infer<typeof createEvalFormSchema>;

export interface CreateEvalDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateEvalFormData) => Promise<void>;
  isLoading: boolean;
  initialValues?: Partial<CreateEvalFormData>;
  isFetchingSuggestion?: boolean;
}

export const CreateEvalDialog: FC<CreateEvalDialogProps> = ({
  open,
  onClose,
  onSubmit,
  isLoading = false,
  initialValues,
  isFetchingSuggestion = false,
}) => {
  const form = useForm<CreateEvalFormData>({
    resolver: zodResolver(createEvalFormSchema),
    defaultValues: {
      name: initialValues?.name || '',
      description: initialValues?.description || '',
      useLiveExecution: initialValues?.useLiveExecution ?? false,
    evaluationCriteria: {
      actionCalling: initialValues?.evaluationCriteria?.actionCalling ?? true,
      actionCallingPolicy: {
        assertAllConsumed:
          initialValues?.evaluationCriteria?.actionCallingPolicy?.assertAllConsumed ?? true,
        allowLlmArgValidation:
          initialValues?.evaluationCriteria?.actionCallingPolicy?.allowLlmArgValidation ?? false,
        allowLlmInterpolation:
          initialValues?.evaluationCriteria?.actionCallingPolicy?.allowLlmInterpolation ?? false,
      },
      flowAdherence: initialValues?.evaluationCriteria?.flowAdherence ?? true,
      responseAccuracy: initialValues?.evaluationCriteria?.responseAccuracy ?? true,
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
    setValue,
  } = form;

  const actionCallingChecked = watch('evaluationCriteria.actionCalling', true);
  const actionCallingAssertAllConsumedChecked = watch(
    'evaluationCriteria.actionCallingPolicy.assertAllConsumed',
    true,
  );
  const actionCallingAllowLlmArgValidationChecked = watch(
    'evaluationCriteria.actionCallingPolicy.allowLlmArgValidation',
    false,
  );
  const actionCallingAllowLlmInterpolationChecked = watch(
    'evaluationCriteria.actionCallingPolicy.allowLlmInterpolation',
    false,
  );
  const flowAdherenceChecked = watch('evaluationCriteria.flowAdherence', true);
  const responseAccuracyChecked = watch('evaluationCriteria.responseAccuracy', true);

  const [showActionCallingAdvanced, setShowActionCallingAdvanced] = useState(false);

  useEffect(() => {
    if (!open) {
      setShowActionCallingAdvanced(false);
    }
  }, [open]);

  useEffect(() => {
    if (open && initialValues) {
      reset({
        name: initialValues.name || '',
        description: initialValues.description || '',
        useLiveExecution: initialValues.useLiveExecution ?? false,
        evaluationCriteria: {
          actionCalling: initialValues.evaluationCriteria?.actionCalling ?? true,
          actionCallingPolicy: {
            assertAllConsumed:
              initialValues.evaluationCriteria?.actionCallingPolicy?.assertAllConsumed ?? true,
            allowLlmArgValidation:
              initialValues.evaluationCriteria?.actionCallingPolicy?.allowLlmArgValidation ?? false,
            allowLlmInterpolation:
              initialValues.evaluationCriteria?.actionCallingPolicy?.allowLlmInterpolation ?? false,
          },
          flowAdherence: initialValues.evaluationCriteria?.flowAdherence ?? true,
          responseAccuracy: initialValues.evaluationCriteria?.responseAccuracy ?? true,
          responseAccuracyExpectation:
            initialValues.evaluationCriteria?.responseAccuracyExpectation ?? '',
        },
      });

      if (initialValues.evaluationCriteria?.responseAccuracyExpectation !== undefined) {
        setValue(
          'evaluationCriteria.responseAccuracyExpectation',
          initialValues.evaluationCriteria.responseAccuracyExpectation ?? '',
          { shouldDirty: false, shouldTouch: false },
        );
      }
    }
  }, [open, initialValues, reset, setValue]);

  const handleFormSubmit = handleSubmit(async (data) => {
    await onSubmit(data);
    reset({
      name: '',
      description: '',
      useLiveExecution: false,
      evaluationCriteria: {
        actionCalling: true,
        actionCallingPolicy: {
          assertAllConsumed: true,
          allowLlmArgValidation: false,
          allowLlmInterpolation: false,
        },
        flowAdherence: true,
        responseAccuracy: true,
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
        actionCalling: true,
        actionCallingPolicy: {
          assertAllConsumed: true,
          allowLlmArgValidation: false,
          allowLlmInterpolation: false,
        },
        flowAdherence: true,
        responseAccuracy: true,
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
            <Typography variant="display-large">Creating Your Evaluation</Typography>
            <Typography variant="body-medium">Your Evaluation will be available in a few seconds.</Typography>
          </Box>
        </Dialog.Content>
        
        <Dialog.Actions>
          <Button 
            variant="secondary" 
            onClick={handleClose}
            disabled
          >
            Cancel
          </Button>
        </Dialog.Actions>
      </Dialog>
    );
  }

  if (isFetchingSuggestion) {
    return (
      <Dialog width={800} open={open} onClose={handleClose}>
        <Dialog.Header>
          <Dialog.Header.Title title="" />
        </Dialog.Header>
        
        <Dialog.Content>
          <Box display="flex" flexDirection="column" alignItems="center" gap="$16" padding="$32">
            <Progress size="large" />
          </Box>
        </Dialog.Content>
        
        <Dialog.Actions>
          <Button 
            variant="secondary" 
            onClick={handleClose}
            disabled
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
            <Typography variant='display-small'>Add to Evaluations</Typography>
          </Box>
        } />
        <Dialog.Header.Description>Provide a name and description of this evaluation.</Dialog.Header.Description>
      </Dialog.Header>
      
      <Dialog.Content>
        <Form onSubmit={handleFormSubmit}>
          <Form.Fieldset>
            <Input 
              label="Name" 
              description="Enter a unique name for this evaluation."
              disabled={isLoading}
              error={errors.name?.message}
              {...register('name')} 
            />
            <Input 
              label="Description" 
              description="Provide a description of this evaluation."
              disabled={isLoading}
              error={errors.description?.message}
              {...register('description')} 
            />
            <Controller
              name="useLiveExecution"
              control={control}
              render={({ field: { value, onChange } }) => (
                <Checkbox
                  label="Execute tools live during evaluation"
                  description="When enabled, the evaluation will run real tool calls instead of replaying recorded outputs."
                  checked={value}
                  onChange={(event) => onChange(event.target.checked)}
                  disabled={isLoading}
                />
              )}
            />
            <Box display="flex" flexDirection="column" gap="$8">
              <Typography variant="display-small">Evaluation criteria</Typography>
              <Typography variant="body-small">
                Select which checks should run during this evaluation. Leave all unchecked to run without automated checks.
              </Typography>
              {(() => {
                const { onChange, onBlur, ref, name } = register('evaluationCriteria.actionCalling');
                return (
                  <Checkbox
                    label="Action calling"
                    description="Check that tool calls match the golden run."
                    name={name}
                    checked={actionCallingChecked}
                    onBlur={onBlur}
                    onChange={onChange}
                    disabled={isLoading}
                    ref={ref}
                  />
                );
              })()}
              <Box display="flex" flexDirection="column" gap="$4" paddingLeft="$8">
                <Button
                  variant="ghost"
                  size="small"
                  onClick={() => setShowActionCallingAdvanced((prev) => !prev)}
                  disabled={isLoading || !actionCallingChecked}
                >
                  {showActionCallingAdvanced ? 'Hide advanced settings' : 'Show advanced settings'}
                </Button>
                {showActionCallingAdvanced && (
                  <Box display="flex" flexDirection="column" gap="$4" paddingLeft="$4">
                    {(() => {
                      const { onChange, onBlur, ref, name } = register(
                        'evaluationCriteria.actionCallingPolicy.assertAllConsumed',
                      );
                      return (
                        <Checkbox
                          label="Assert all recorded tool calls are consumed"
                          description="Ensures the replay uses every expected tool call."
                          name={name}
                          checked={actionCallingAssertAllConsumedChecked}
                          onBlur={onBlur}
                          onChange={onChange}
                          disabled={isLoading || !actionCallingChecked}
                          ref={ref}
                        />
                      );
                    })()}
                    {(() => {
                      const { onChange, onBlur, ref, name } = register(
                        'evaluationCriteria.actionCallingPolicy.allowLlmArgValidation',
                      );
                      return (
                        <Checkbox
                          label="Allow LLM argument validation"
                          description="Let an LLM validate tool call arguments when mismatches occur."
                          name={name}
                          checked={actionCallingAllowLlmArgValidationChecked}
                          onBlur={onBlur}
                          onChange={onChange}
                          disabled={isLoading || !actionCallingChecked}
                          ref={ref}
                        />
                      );
                    })()}
                    {(() => {
                      const { onChange, onBlur, ref, name } = register(
                        'evaluationCriteria.actionCallingPolicy.allowLlmInterpolation',
                      );
                      return (
                        <Checkbox
                          label="Allow LLM interpolation"
                          description="Let an LLM propose outputs when replay drifts from the recorded calls."
                          name={name}
                          checked={actionCallingAllowLlmInterpolationChecked}
                          onBlur={onBlur}
                          onChange={onChange}
                          disabled={isLoading || !actionCallingChecked}
                          ref={ref}
                        />
                      );
                    })()}
                  </Box>
                )}
              </Box>
              {(() => {
                const { onChange, onBlur, ref, name } = register('evaluationCriteria.flowAdherence');
                return (
                  <Checkbox
                    label="Flow adherence"
                    description="Compare the conversation flow to the recorded scenario."
                    name={name}
                    checked={flowAdherenceChecked}
                    onBlur={onBlur}
                    onChange={onChange}
                    disabled={isLoading}
                    ref={ref}
                  />
                );
              })()}
              {(() => {
                const { onChange, onBlur, ref, name } = register('evaluationCriteria.responseAccuracy');
                return (
                  <Checkbox
                    label="Response accuracy"
                    description="Score the agent response against the expectations you provide."
                    name={name}
                    checked={responseAccuracyChecked}
                    onBlur={onBlur}
                    onChange={onChange}
                    disabled={isLoading}
                    ref={ref}
                  />
                );
              })()}
              <Input
                label="Response accuracy expectation"
                description="Describe what a correct agent response should include."
                rows={4}
                disabled={isLoading || !responseAccuracyChecked}
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
        >
          Add Evaluation
        </Button>
        <Button 
          variant="secondary" 
          onClick={handleClose}
          disabled={isLoading}
        >
          Cancel
        </Button>
      </Dialog.Actions>
    </Dialog>
  );
};

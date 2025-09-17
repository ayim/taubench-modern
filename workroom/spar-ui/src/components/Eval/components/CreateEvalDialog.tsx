import { FC, useEffect } from "react";
import z from "zod";
import { Dialog, Box, Typography, Form, Input, Button, Progress } from "@sema4ai/components";
import { IconChemicalBottle } from "@sema4ai/icons";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

const createEvalFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name must be less than 100 characters'),
  description: z.string().min(1, 'Description is required').max(500, 'Description must be less than 500 characters'),
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
      description: initialValues?.description || '' 
    },
    mode: 'onChange',
  });

  const {
    register,
    formState: { errors, isValid },
    handleSubmit,
    reset,
  } = form;

  useEffect(() => {
    if (open && initialValues) {
      reset({
        name: initialValues.name || '',
        description: initialValues.description || ''
      });
    }
  }, [open, initialValues, reset]);

  const handleFormSubmit = handleSubmit(async (data) => {
    await onSubmit(data);
    reset();
  });

  const handleClose = () => {
    reset();
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
              rows={6}
              disabled={isLoading}
              error={errors.description?.message}
              {...register('description')} 
            />
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
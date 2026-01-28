import { DragEvent, FC, useEffect, useState } from 'react';
import z from 'zod';
import { Dialog, Box, Typography, Form, Input, Button, Progress } from '@sema4ai/components';
import { IconPlus, IconTrash, IconMenu } from '@sema4ai/icons';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

const upsertSectionFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name must be less than 100 characters'),
  prompts: z
    .array(
      z.object({
        text: z.string().min(1, 'Prompt text is required'),
      }),
    )
    .min(1, 'At least one prompt is required'),
});

export type UpsertSectionFormData = z.infer<typeof upsertSectionFormSchema>;

export interface UpsertSectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: UpsertSectionFormData) => Promise<void>;
  isLoading: boolean;
  initialValues?: Partial<UpsertSectionFormData>;
  isEditing?: boolean;
}

export const UpsertSectionDialog: FC<UpsertSectionDialogProps> = ({
  open,
  onClose,
  onSubmit,
  isLoading = false,
  initialValues,
  isEditing = false,
}) => {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const form = useForm<UpsertSectionFormData>({
    resolver: zodResolver(upsertSectionFormSchema),
    defaultValues: {
      name: initialValues?.name || '',
      prompts: initialValues?.prompts ?? [{ text: '' }],
    },
    mode: 'onChange',
  });

  const {
    register,
    control,
    formState: { errors, isValid },
    handleSubmit,
    reset,
  } = form;

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'prompts',
  });

  useEffect(() => {
    if (open) {
      reset({
        name: initialValues?.name || '',
        prompts: initialValues?.prompts ?? [{ text: '' }],
      });
    }
  }, [open, initialValues, reset]);

  const addPrompt = () => {
    append({ text: '' });
  };

  const removePrompt = (index: number) => {
    if (fields.length > 1) {
      remove(index);
    }
  };

  const handleDragStart = (e: DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: DragEvent, targetIndex: number) => {
    e.preventDefault();

    if (draggedIndex === null || draggedIndex === targetIndex) {
      setDraggedIndex(null);
      return;
    }

    const currentValues = form.getValues().prompts;
    const newPrompts = [...currentValues];

    const [draggedItem] = newPrompts.splice(draggedIndex, 1);
    newPrompts.splice(targetIndex, 0, draggedItem);

    form.setValue('prompts', newPrompts);

    setDraggedIndex(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

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
          </Box>
        </Dialog.Content>

        <Dialog.Actions>
          <Button variant="secondary" onClick={handleClose} disabled>
            Cancel
          </Button>
        </Dialog.Actions>
      </Dialog>
    );
  }

  return (
    <Dialog width={800} open={open} onClose={handleClose}>
      <Dialog.Header>
        <Dialog.Header.Title
          title={
            <Box display="flex" alignItems="center" gap="$8">
              <Typography variant="display-small">{isEditing ? 'Edit Section' : 'Add New Section'}</Typography>
            </Box>
          }
        />
      </Dialog.Header>

      <Dialog.Content>
        <Form onSubmit={handleFormSubmit}>
          <Form.Fieldset>
            <Input
              label="Name"
              description="Unique name for this section for prompts"
              disabled={isLoading}
              error={errors.name?.message}
              {...register('name')}
            />

            <Box display="flex" flexDirection="column" gap="$8">
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Typography variant="body-medium" fontWeight="medium">
                  Prompts
                </Typography>
                <Button variant="ghost" size="medium" onClick={addPrompt} disabled={isLoading}>
                  <IconPlus size={16} />
                  Add Prompt
                </Button>
              </Box>

              {fields.map((field, index) => (
                <Box
                  key={field.id}
                  display="flex"
                  alignItems="center"
                  gap="$8"
                  padding="$8"
                  draggable
                  onDragStart={(e: DragEvent) => handleDragStart(e, index)}
                  onDragOver={handleDragOver}
                  onDrop={(e: DragEvent) => handleDrop(e, index)}
                  onDragEnd={handleDragEnd}
                  style={{
                    opacity: draggedIndex === index ? 0.5 : 1,
                    cursor: 'grab',
                  }}
                >
                  <Box style={{ cursor: 'grab' }}>
                    <IconMenu size={24} />
                  </Box>

                  <Box flex="1">
                    <Input
                      label=""
                      disabled={isLoading}
                      error={errors.prompts?.[index]?.text?.message}
                      {...register(`prompts.${index}.text` as const)}
                    />
                  </Box>

                  <Button
                    variant="ghost"
                    size="small"
                    onClick={() => removePrompt(index)}
                    disabled={isLoading || fields.length <= 1}
                    style={{ color: '#ef4444' }}
                  >
                    <IconTrash size={24} />
                  </Button>
                </Box>
              ))}

              {errors.prompts && (
                <Typography variant="body-small" color="content.error">
                  {errors.prompts.message}
                </Typography>
              )}
            </Box>
          </Form.Fieldset>
        </Form>
      </Dialog.Content>

      <Dialog.Actions>
        <Button type="submit" onClick={handleFormSubmit} disabled={!isValid || isLoading} loading={isLoading} round>
          {isEditing ? 'Update Section' : 'Add Section'}
        </Button>
        <Button variant="secondary" onClick={handleClose} disabled={isLoading} round>
          Cancel
        </Button>
      </Dialog.Actions>
    </Dialog>
  );
};

import { FC, useCallback } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Code, Dialog, Form, Input, Typography, useSnackbar } from '@sema4ai/components';
import { IconClose, IconPlus } from '@sema4ai/icons';
import { IconAnyFile, IconPDF } from '@sema4ai/icons/logos';
import { FileRejection, useDropzone } from 'react-dropzone';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { useCreateWorkItemMutation } from '../../queries/workItem';
import { useParams } from '../../hooks/useParams';
import { useNavigate } from '../../hooks/useNavigate';

interface CreateWorkItemDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

type WorkerItemFormValues = {
  message: string;
  payload?: string;
  files?: File[];
};

export const CreateWorkItemDialog: FC<CreateWorkItemDialogProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { agentId } = useParams('/worker/$agentId');
  const { addSnackbar } = useSnackbar();

  const { mutateAsync: createWorkItemAsync, isPending: isCreatingWorkItem } = useCreateWorkItemMutation({ agentId });

  const createWorkItemFormSchema = z.object({
    message: z.string().trim().min(1, 'Message is required'),
    payload: z
      .string()
      .optional()
      .refine(
        (val) => {
          if (val === undefined || val === null) return true;
          if (val.trim() === '') return true;
          try {
            JSON.parse(val);
            return true;
          } catch {
            return false;
          }
        },
        { message: 'Payload must be valid JSON' },
      ),
    files: z.array(z.instanceof(File)).optional(),
  });

  const form = useForm<WorkerItemFormValues>({
    resolver: zodResolver(createWorkItemFormSchema),
    defaultValues: {
      message: '',
      payload: '',
      files: [],
    },
    mode: 'onChange',
  });

  const onSubmit = form.handleSubmit(async (values) => {
    createWorkItemAsync(values, {
      onSuccess: (result) => {
        addSnackbar({ message: 'Work item created successfully', variant: 'success' });
        navigate({ to: '/worker/$agentId/$workItemId', params: { agentId, workItemId: result.work_item_id } });
      },
      onError: (error) => {
        const errorMessage = error instanceof Error ? error.message : 'Failed to create work item';
        addSnackbar({ message: errorMessage, variant: 'danger' });
      },
    });
  });

  const handleFileUpload = useCallback(
    (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      // Handle rejected files (too large, wrong type, etc.)
      fileRejections?.forEach(() => {
        addSnackbar({
          message: 'Failed to Upload File',
          variant: 'danger',
        });
      });

      // Add accepted files to the form
      if (acceptedFiles.length > 0) {
        form.setValue('files', [...(form.getValues('files') || []), ...acceptedFiles]);
      }
    },
    [form.getValues, form.setValue],
  );

  const { getInputProps, open } = useDropzone({
    multiple: true,
    maxSize: 100_000_000,
    onDrop: handleFileUpload,
    // Disable click and keydown behavior since we're using a button
    noClick: true,
    noKeyboard: true,
    disabled: isCreatingWorkItem,
  });

  const removeFile = useCallback(
    (fileName: string) => {
      form.setValue(
        'files',
        (form.getValues('files') || []).filter((f) => f.name !== fileName),
      );
    },
    [form.setValue, form.getValues],
  );

  const handleCancel = useCallback(() => {
    form.reset();
    onClose();
  }, [onClose, form.reset]);

  return (
    <Dialog open={isOpen} onClose={onClose} width={800}>
      <Form onSubmit={onSubmit} width="100%" busy={isCreatingWorkItem} height="100%">
        <Dialog.Header>
          <Box display="flex" flexDirection="column" gap={16} px={4}>
            <Dialog.Header.Title title={<Typography fontWeight="bold">Create Work Item</Typography>} />
            <Box display="flex" flexDirection="row" gap={2}>
              <Typography>API-based Work Items are JSON structured data, processed by the agent.</Typography>
            </Box>
          </Box>
        </Dialog.Header>
        <Dialog.Content>
          <Box display="flex" flexDirection="column" gap={16} paddingTop={12} px={4} pb={2}>
            <Input
              rows={4}
              label="Message"
              description="Provide the agent with instructions on how to process this work item."
              {...form.register('message')}
              name="message"
              error={form.formState.errors.message?.message}
            />
            <Code
              aria-label="Payload"
              value={form.getValues('payload') || ''}
              onChange={(value) => form.setValue('payload', value)}
              lineNumbers={false}
              lang="JSON"
              rows={6}
              label="Payload"
              description="Optional JSON data structure (must be valid JSON if provided)"
              error={form.formState.errors.payload?.message}
            />
            <Box display="flex" flexDirection="column" gap={8}>
              <Typography variant="body-medium" fontWeight="medium">
                Files
              </Typography>

              <Box display="flex" flexDirection="row" gap={4} flexWrap="wrap" alignItems="center">
                {/* Display uploaded files */}
                {(form.watch('files') ?? []).length > 0 && (
                  <Box display="flex" flexDirection="row" gap={4} flexWrap="wrap">
                    {(form.watch('files') ?? []).map((file) => (
                      <Box
                        key={`${file.name}-${file.lastModified}`}
                        display="flex"
                        flexDirection="row"
                        alignItems="center"
                        justifyContent="space-between"
                        px={12}
                        py={4}
                        backgroundColor="background.subtle.light"
                        borderRadius={8}
                      >
                        <Box display="flex" flexDirection="row" alignItems="center" gap={8}>
                          {file.type === 'application/pdf' ? <IconPDF size={24} /> : <IconAnyFile size={24} />}
                          <Typography variant="body-small">{file.name}</Typography>
                        </Box>
                        <Button
                          variant="ghost"
                          size="small"
                          aria-label="Remove file"
                          icon={IconClose}
                          onClick={() => removeFile(file.name)}
                        />
                      </Box>
                    ))}
                  </Box>
                )}

                <Box display="flex" flexDirection="row" gap={2}>
                  <input {...getInputProps()} />
                  <Button variant="ghost" icon={IconPlus} onClick={open} disabled={isCreatingWorkItem}>
                    File
                  </Button>
                </Box>
              </Box>
            </Box>
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" round type="submit" loading={isCreatingWorkItem}>
            Create
          </Button>
          <Button variant="secondary" round onClick={handleCancel}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};

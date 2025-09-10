import { zodResolver } from '@hookform/resolvers/zod';
import type { components } from '@sema4ai/agent-server-interface';
import { Box, Button, Code, Dialog, Form, Input, Progress, Typography, useSnackbar } from '@sema4ai/components';
import { IconClose, IconPlus } from '@sema4ai/icons';
import { IconAnyFile, IconPDF } from '@sema4ai/icons/logos';
import { FC, useCallback, useEffect, useState } from 'react';
import { FileRejection, useDropzone } from 'react-dropzone';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useCreateWorkItemMutation, useUploadWorkItemFileMutation } from '../../queries/workItem';

interface CreateWorkItemDialogProps {
  isOpen: boolean;
  onClose: () => void;
  agentId: string;
}

type WorkerItemFormValues = {
  message: string;
  payload?: string;
  files?: File[];
};

type CreateWorkItemPayload = components['schemas']['CreateWorkItemPayload'];

export const CreateWorkItemDialog: FC<CreateWorkItemDialogProps> = ({ isOpen, onClose, agentId }) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const { addSnackbar } = useSnackbar();
  
  const { mutateAsync: createWorkItem, isPending: isCreatingWorkItem } = useCreateWorkItemMutation({ agentId });
  const { mutateAsync: uploadWorkItemFile, isPending: isUploadingFile } = useUploadWorkItemFileMutation({});
  
  const isProcessingMutation = isCreatingWorkItem || isUploadingFile;

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


  // Helper function to create the base work item payload
  const createBaseWorkItemPayload = useCallback(
    (values: WorkerItemFormValues) => {
      const payload: CreateWorkItemPayload = {
        agent_id: agentId,
        messages: [
          {
            role: 'user',
            content: [{ kind: 'text', text: values.message, complete: true }],
            complete: true,
            commited: true,
          },
        ],
      };

      // Add payload if provided; JSON validity is enforced by the form schema
      if (values.payload && values.payload.trim()) {
        const parsedPayload = JSON.parse(values.payload);
        payload.payload = parsedPayload;
      }

      return payload;
    },
    [agentId],
  );

  // Submit without files - direct work item creation
  const submitWithoutFiles = useCallback(
    async (values: WorkerItemFormValues) => {
      const payload = createBaseWorkItemPayload(values);
      return createWorkItem({ payload });
    },
    [createWorkItem, createBaseWorkItemPayload],
  );

  // Submit with files - file upload flow
  const submitWithFiles = useCallback(
    async (values: WorkerItemFormValues) => {
      if (!values.files || values.files.length === 0) {
        throw new Error('No files provided for file upload flow');
      }

      let workItemId: string | null = null;
      // Upload first file to get work_item_id
      const firstFileResponse = await uploadWorkItemFile({ file: values.files[0] });

      if (!firstFileResponse?.work_item_id) {
        throw new Error('Failed to get Work Item ID from file upload');
      }

      workItemId = String(firstFileResponse.work_item_id);

      // Upload remaining files in parallel
      if (values.files.length > 1) {
        const remainingFiles = values.files.slice(1);
        const uploadPromises = remainingFiles.map(async (file) => {
          return uploadWorkItemFile({ file, workItemId });
        });

        try {
          await Promise.all(uploadPromises);
        } catch (error) {
          throw new Error('Failed to upload some files');
        }
      }

      // Create the work item with the work_item_id
      const payload = createBaseWorkItemPayload(values);
      payload.work_item_id = workItemId;

      return createWorkItem({ payload });
    },
    [uploadWorkItemFile, createWorkItem, createBaseWorkItemPayload],
  );


  const submitWorkItem = useCallback(
    async (values: WorkerItemFormValues) => {
      setIsProcessing(true);
      setProcessingStatus('Processing...');

      try {
        let result;

        if (!values.files || values.files.length === 0) {
          // Flow 1: No files - create work item directly
          setProcessingStatus('Creating work item...');
          result = await submitWithoutFiles(values);
        } else {
          // Flow 2: Has files - handle file upload flow
          setProcessingStatus('Uploading files...');
          result = await submitWithFiles(values);
        }

        return result;
      } finally {
        setIsProcessing(false);
        setProcessingStatus('');
      }
    },
    [submitWithoutFiles, submitWithFiles],
  );

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await submitWorkItem(values);
      addSnackbar({ message: 'Work item created successfully', variant: 'success' });
      form.reset();
      onClose();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create work item';
      addSnackbar({ message: errorMessage, variant: 'danger' });
    }
  });

  useEffect(() => {
    if (!isOpen) {
      form.reset();
      setIsProcessing(false);
      setProcessingStatus('');
    }
  }, [isOpen, form.reset]);

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
    disabled: isProcessing || isProcessingMutation,
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
      {isProcessing ? (
        <Dialog.Content>
          <Box display="flex" flexDirection="column" gap={4} pt={12} pb={36} alignItems="center">
            <Progress />
            <Typography color="content.subtle.light">{processingStatus}</Typography>
          </Box>
        </Dialog.Content>
      ) : (
        <Form onSubmit={onSubmit} width="100%" busy={isProcessing || isProcessingMutation} height="100%" >
          <Dialog.Header>
            <Box display="flex" flexDirection="column" gap={16} px={4} >
              <Dialog.Header.Title title={<Typography fontWeight="bold">Create Work Item</Typography>} />
              <Box display="flex" flexDirection="row" gap={2}>
                <Typography>API-based Work Items are JSON structured data, processed by the agent.</Typography>
              </Box>
            </Box>
          </Dialog.Header>
          <Dialog.Content>
            <Box display="flex" flexDirection="column" gap={16} paddingTop={12} px={4} pb={2} >
              <Input
                rows={4}
                label="Message"
                description="Provide the agent with instructions on how to process this work item."
                {...form.register('message')}
                name="message"
                disabled={isProcessing || isProcessingMutation}
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
                            disabled={isProcessing || isProcessingMutation}
                          />
                        </Box>
                      ))}
                    </Box>
                  )}

                  {/* Add File button */}
                  <Box display="flex" flexDirection="row" gap={2}>
                    <input {...getInputProps()} />
                    <Button variant="ghost" icon={IconPlus} onClick={open} disabled={isProcessing}>
                      File
                    </Button>
                  </Box>
                </Box>
              </Box>
            </Box>
          </Dialog.Content>
          <Dialog.Actions>
            <Button variant="primary" round type="submit">
              Create
            </Button>
            <Button variant="secondary" round onClick={handleCancel}>
              Cancel
            </Button>
          </Dialog.Actions>
        </Form>
      )}
    </Dialog>
  );
};
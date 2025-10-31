import { Button, Dialog, Form, Input, Box, Typography, Progress, useSnackbar } from '@sema4ai/components';
import { IconSparkles2 } from '@sema4ai/icons';
import { FC, useCallback, useState, useEffect } from 'react';
import { useDataModelDescriptionGeneration } from '../../hooks/useDocumentIntelligenceFlows';
import { toSnakeCase } from '../../utils/dataTransformations';

interface DataModelNameDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (name: string, description: string) => void;
  fileRef: File | null;
  threadId: string;
  agentId: string;
  isProcessing?: boolean;
  error?: string;
  processingStep?: string;
}

export const DataModelNameDialog: FC<DataModelNameDialogProps> = ({
  open,
  onClose,
  onSave,
  fileRef,
  threadId,
  agentId,
  isProcessing = false,
  error,
  processingStep,
}) => {
  const { addSnackbar } = useSnackbar();
  const {
    generateDataModelDescription,
    isLoading: isGeneratingDescription,
  } = useDataModelDescriptionGeneration();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [errors, setErrors] = useState<{ name?: string; description?: string }>({});
  const [isInitialized, setIsInitialized] = useState(false);


  useEffect(() => {
    if (fileRef) {
      const suggestedName = `${toSnakeCase(fileRef.name)}_data_model`;
      setName(suggestedName);
    }
  }, [fileRef]);

  useEffect(() => {
    if (open && !isInitialized && fileRef && threadId && agentId) {
      setIsInitialized(true);

      const generateDescription = async () => {
        try {
          const generatedDescription = await generateDataModelDescription({
            threadId,
            agentId,
            fileRef: fileRef.name,
          });
          setDescription(generatedDescription);
        } catch (err) {
          addSnackbar({ message: `Failed to generate description: ${err}`, variant: 'danger', close: true });
        }
      };

      generateDescription();
    }
  }, [open, isInitialized, fileRef, threadId, agentId]);


  useEffect(() => {
    if (!open) {
      setDescription('');
      setErrors({});
      setIsInitialized(false);
    }
  }, [open]);

  const handleSave = useCallback(() => {
    const newErrors: { name?: string; description?: string } = {};

    if (!name.trim()) {
      newErrors.name = 'Data model name is required';
    }

    // TODO: Wire backend normalization logic to frontend validation
    // Backend has additional validation rules (length limits, character restrictions, etc.)
    // that should be reflected in frontend validation to prevent submission failures

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    onSave(name.trim(), description.trim());
    // Close dialog after save is initiated (loading screen will show in background)
    onClose();
  }, [name, description, onSave, onClose]);

  const handleCancel = useCallback(() => {
      if (fileRef) {
        const suggestedName = `${toSnakeCase(fileRef.name)}_data_model`;
        setName(suggestedName);
      }
      setDescription('');
      setIsInitialized(false);
    setErrors({});
    onClose();
  }, [fileRef, onClose]);


  const handleDialogClose = useCallback(() => {
    if (isProcessing) {
      return;
    }
    handleCancel();
  }, [isProcessing, handleCancel]);

  return (
    <Dialog open={open} onClose={handleDialogClose} width={600}>
      <Dialog.Header>
        <Dialog.Header.Title title="Create Your Model Name and Description" />
      </Dialog.Header>
      <Dialog.Content>
        <Form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
          maxWidth="100%"
        >
          <Form.Fieldset>
            <Input
              label="Data Model Name"
              placeholder="Enter Model Name"
              description="Enter a unique name for your data model"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (errors.name) {
                  setErrors((prev) => ({ ...prev, name: undefined }));
                }
              }}
              error={errors.name || error}
              disabled={isProcessing}
            />

            <Input
              label="Description"
              description={isGeneratingDescription || description ? '' : 'Provide a description for this data model'}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isProcessing || isGeneratingDescription}
              rows={6}
              style={{ fontSize: '14px', lineHeight: '1.5' }}
            />

            {/* Description Generation Status */}
            {isGeneratingDescription && (
              <Box height="100%">
                <Box display="flex" gap="$8" alignItems="center" marginBottom="$8">
                  <Progress id="description-generation" size="medium" />
                  <Typography fontSize="$14" fontWeight="medium" color="content.subtle.light">
                    Generating a description for your data model...
                  </Typography>
                </Box>
              </Box>
            )}

            {/* Processing Status */}
            {isProcessing && processingStep && (
              <Box height="100%">
                <Box display="flex" gap="$8" alignItems="center" marginBottom="$8">
                  <IconSparkles2 color="content.subtle.light" />
                  <Typography fontSize="$16" fontWeight="medium" color="content.subtle.light">
                    {processingStep}
                  </Typography>
                </Box>
                <Box display="flex" gap="$8">
                  <Progress id="data-model-name-dialog" />
                </Box>
              </Box>
            )}
          </Form.Fieldset>
        </Form>
      </Dialog.Content>
      <Dialog.Actions>
        <Button
          variant="primary"
          round
          onClick={handleSave}
          disabled={isProcessing || isGeneratingDescription}
          loading={isProcessing}
        >
          Save
        </Button>
        <Button variant="secondary" round onClick={handleCancel} disabled={isProcessing}>
          Cancel
        </Button>
      </Dialog.Actions>
    </Dialog>
  );
};

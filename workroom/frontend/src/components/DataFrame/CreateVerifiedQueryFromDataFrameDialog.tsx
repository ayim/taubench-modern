import { FC, useEffect, useState, useMemo, useCallback } from 'react';
import { Box, Button, Dialog, Progress, Select, Typography, useSnackbar } from '@sema4ai/components';

import { useAgentSemanticDataQuery, VerifiedQuery, useVerifyVerifiedQueryMutation } from '~/queries/semanticData';
import { useDataFrameAsValidatedQuery, useSaveVerifiedQueryMutation } from '~/queries/dataFrames';
import { QueryError, getSnackbarContent } from '~/queries/shared';
import {
  VerifiedQueryForm,
  FormData,
} from '../SemanticData/SemanticDataConfiguration/components/ModelEdition/components/VerifiedQueryForm';

interface CreateVerifiedQueryDialogProps {
  open: boolean;
  onClose: () => void;
  threadId: string;
  agentId: string;
  dataFrameName: string;
}

export const CreateVerifiedQueryFromDataFrameDialog: FC<CreateVerifiedQueryDialogProps> = ({
  open,
  onClose,
  threadId,
  agentId,
  dataFrameName,
}) => {
  const [selectedModelId, setSelectedModelId] = useState<string>('');
  const [showForm, setShowForm] = useState(false);
  const { data: semanticModels = [], isLoading } = useAgentSemanticDataQuery({ agentId });
  const { addSnackbar } = useSnackbar();
  const saveMutation = useSaveVerifiedQueryMutation({});
  const verifyMutation = useVerifyVerifiedQueryMutation({});
  const [formData, setFormData] = useState<FormData | null>(null);
  const [isFormNotEmpty, setIsFormNotEmpty] = useState(false);
  const [errors, setErrors] = useState<{
    sql_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    nlq_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    name_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    parameter_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
  }>({});

  const selectedModel = useMemo(() => {
    return semanticModels.find((model) => model.id === selectedModelId);
  }, [semanticModels, selectedModelId]);

  const {
    data: validatedQueryResponse,
    isLoading: isLoadingQuery,
    error: queryError,
  } = useDataFrameAsValidatedQuery({
    threadId,
    dataFrameName,
    enabled: showForm && !!selectedModelId,
  });

  const initialQuery = validatedQueryResponse?.verified_query;

  const memoizedInitialQuery = useMemo(
    () =>
      initialQuery
        ? {
            ...initialQuery,
            sql_errors: initialQuery.sql_errors ?? undefined,
            nlq_errors: initialQuery.nlq_errors ?? undefined,
            name_errors: initialQuery.name_errors ?? undefined,
          }
        : undefined,
    [initialQuery],
  );

  const handleFormDataChange = useCallback((data: FormData, isNonEmpty: boolean) => {
    setFormData(data);
    setIsFormNotEmpty(isNonEmpty);
  }, []);

  const handleValidationErrorsChange = useCallback(
    (validationErrors: {
      sql_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
      nlq_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
      name_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    }) => {
      setErrors(validationErrors);
    },
    [],
  );

  // Auto-detect semantic data model from the data frame
  const { data: autoDetectResponse, isLoading: isAutoDetecting } = useDataFrameAsValidatedQuery({
    threadId,
    dataFrameName,
    enabled: open && !showForm && !selectedModelId,
  });

  // Auto-select SDM when there's only one model OR when a model is detected
  useEffect(() => {
    if (semanticModels.length === 0 || showForm || selectedModelId) {
      return;
    }

    // If we have a detected SDM name, check if it exists in the available models
    const detectedSdmName = autoDetectResponse?.semantic_data_model_name;
    if (detectedSdmName) {
      const detectedModel = semanticModels.find((model) => model.name === detectedSdmName);
      if (detectedModel) {
        // Auto-select the detected model and show the form directly
        setSelectedModelId(detectedModel.id);
        setShowForm(true);
        return;
      }
      // If detected model doesn't exist anymore, user will need to select manually
    }

    // Fallback: if only one model exists, auto-select it
    if (semanticModels.length === 1) {
      setSelectedModelId(semanticModels[0].id);
      setShowForm(true);
    }
  }, [semanticModels, selectedModelId, showForm, autoDetectResponse, open]);

  const handleModelSelect = (modelId: string) => {
    setSelectedModelId(modelId);
    setShowForm(true);
  };

  const filterErrors = useCallback(
    (errorList?: Array<{ message: string; level: 'error' | 'warning' }>, level: 'error' | 'warning' = 'error') => {
      if (!errorList || errorList.length === 0) return [];
      return errorList.filter((error) => error.level === level);
    },
    [],
  );

  const handleClose = useCallback(() => {
    setSelectedModelId('');
    setShowForm(false);
    setFormData(null);
    setErrors({});
    onClose();
  }, [onClose]);

  const handleBack = useCallback(() => {
    setShowForm(false);
    setErrors({});
    setFormData(null);
  }, []);

  const handleSave = useCallback(async () => {
    if (!selectedModelId || !formData) {
      addSnackbar({
        message: `No semantic data model selected or form data missing -- selectedModelId: ${selectedModelId}, formData: ${formData}`,
        variant: 'danger',
      });
      return;
    }

    if (!isFormNotEmpty) {
      addSnackbar({
        message: 'Please fill in all required fields',
        variant: 'danger',
      });
      return;
    }

    const queryToVerify: VerifiedQuery = {
      name: formData.name.trim(),
      nlq: formData.nlq.trim(),
      sql: formData.sql.trim(),
      verified_at: initialQuery?.verified_at || '',
      verified_by: initialQuery?.verified_by || '',
      parameters: initialQuery?.parameters ?? undefined,
    };

    if (!selectedModel) {
      addSnackbar({
        message: 'No semantic data model selected',
        variant: 'danger',
      });
      return;
    }

    try {
      // Verify the query first
      const verifyResponse = await verifyMutation.mutateAsync({
        semantic_data_model: selectedModel,
        verified_query: queryToVerify,
        accept_initial_name: '',
      });

      const verifiedQuery = verifyResponse.verified_query;

      // Check if there are any errors
      const hasErrors =
        filterErrors(verifiedQuery.sql_errors, 'error').length > 0 ||
        filterErrors(verifiedQuery.nlq_errors, 'error').length > 0 ||
        filterErrors(verifiedQuery.name_errors, 'error').length > 0;

      if (hasErrors) {
        // Show errors but don't save
        setErrors({
          sql_errors: verifiedQuery.sql_errors,
          nlq_errors: verifiedQuery.nlq_errors,
          name_errors: verifiedQuery.name_errors,
        });
        return;
      }

      // No errors, save the verified query with verified_at and verified_by from response
      const newQuery: VerifiedQuery = {
        ...queryToVerify,
        name: verifiedQuery.name,
        nlq: verifiedQuery.nlq,
        sql: verifiedQuery.sql,
        verified_at: verifiedQuery.verified_at,
        verified_by: verifiedQuery.verified_by,
        parameters: verifiedQuery.parameters ?? queryToVerify.parameters,
        result_type: verifiedQuery.result_type,
      };

      await saveMutation.mutateAsync({
        threadId,
        verifiedQuery: newQuery,
        semanticDataModelId: selectedModelId,
        agentId,
      });

      addSnackbar({
        message: `Successfully created verified query "${newQuery.name}"`,
        variant: 'success',
      });
      handleClose();
    } catch (error) {
      if (error instanceof QueryError) {
        const snackbarContent = getSnackbarContent(error);
        addSnackbar(snackbarContent);
      } else {
        addSnackbar({
          message: error instanceof Error ? error.message : 'Failed to create verified query',
          variant: 'danger',
        });
      }
      throw error;
    }
  }, [
    selectedModelId,
    formData,
    addSnackbar,
    isFormNotEmpty,
    initialQuery,
    selectedModel,
    verifyMutation,
    filterErrors,
    saveMutation,
    threadId,
    agentId,
    handleClose,
  ]);

  if (isLoading || isAutoDetecting) {
    return <Progress variant="page" />;
  }

  if (semanticModels.length === 0) {
    return (
      <Dialog open={open} onClose={handleClose}>
        <Dialog.Header>
          <Typography fontSize="$20" fontWeight="bold">
            Create Verified Query
          </Typography>
        </Dialog.Header>
        <Dialog.Content>
          <Box display="flex" flexDirection="column" gap="$8" padding="$16">
            <Typography>
              No semantic data models available. Please create a semantic data model to save the verified query.
            </Typography>
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button onClick={handleClose}>Close</Button>
        </Dialog.Actions>
      </Dialog>
    );
  }

  if (showForm && selectedModel && initialQuery) {
    // Show the form with the verified query
    if (isLoadingQuery) {
      return (
        <Dialog open={open} onClose={handleClose} size="x-large">
          <Dialog.Header>
            <Typography fontSize="$20" fontWeight="bold">
              Create Verified Query from Data Frame
            </Typography>
          </Dialog.Header>
          <Dialog.Content>
            <Box display="flex" justifyContent="center" padding="$16">
              <Typography>Loading verified query data...</Typography>
            </Box>
          </Dialog.Content>
        </Dialog>
      );
    }

    if (queryError) {
      return (
        <Dialog open={open} onClose={handleClose} size="x-large">
          <Dialog.Header>
            <Typography fontSize="$20" fontWeight="bold">
              Create Verified Query from Data Frame
            </Typography>
          </Dialog.Header>
          <Dialog.Content>
            <Box display="flex" flexDirection="column" gap="$8" padding="$16">
              <Typography color="content.error">
                {queryError instanceof Error ? queryError.message : 'Failed to load verified query data'}
              </Typography>
            </Box>
          </Dialog.Content>
          <Dialog.Actions>
            {semanticModels.length === 1 ? (
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
            ) : (
              <Button variant="outline" onClick={handleBack}>
                Back
              </Button>
            )}
            <Button onClick={handleClose}>Close</Button>
          </Dialog.Actions>
        </Dialog>
      );
    }

    return (
      <Dialog open={open} onClose={handleClose} size="x-large">
        <Dialog.Header>
          <Typography fontSize="$20" fontWeight="bold">
            Create Verified Query from Data Frame
          </Typography>
        </Dialog.Header>
        <Dialog.Content>
          <Box display="flex" flexDirection="column" gap="$12" padding="$16">
            <Box display="flex" flexDirection="column" gap="$4">
              <Typography variant="body-medium" fontWeight="medium">
                Semantic Data Model:
              </Typography>
              <Typography>{selectedModel.name}</Typography>
            </Box>
            <VerifiedQueryForm
              isNewQuery
              initialQuery={memoizedInitialQuery as VerifiedQuery}
              semanticDataModel={selectedModel}
              verifyMutation={verifyMutation}
              onFormDataChange={handleFormDataChange}
              onValidationErrorsChange={handleValidationErrorsChange}
              errors={errors}
            />
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button
            onClick={handleSave}
            disabled={!isFormNotEmpty || saveMutation.isPending || verifyMutation.isPending}
            loading={saveMutation.isPending || verifyMutation.isPending}
          >
            Save
          </Button>
          {semanticModels.length === 1 ? (
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={saveMutation.isPending || verifyMutation.isPending}
            >
              Cancel
            </Button>
          ) : (
            <Button
              variant="outline"
              onClick={handleBack}
              disabled={saveMutation.isPending || verifyMutation.isPending}
            >
              Back
            </Button>
          )}
        </Dialog.Actions>
      </Dialog>
    );
  }

  // Show model selection
  return (
    <Dialog open={open} onClose={handleClose} size="x-large">
      <Dialog.Header>
        <Typography fontSize="$20" fontWeight="bold">
          Create Verified Query from Data Frame
        </Typography>
      </Dialog.Header>
      <Dialog.Content>
        <Box display="flex" flexDirection="column" gap="$12" padding="$16">
          <Typography>
            Save the data frame &quot;{dataFrameName}&quot; as a verified query in a semantic data model.
          </Typography>

          {semanticModels.length === 1 ? (
            <Box display="flex" flexDirection="column" gap="$4">
              <Typography variant="body-medium" fontWeight="medium">
                Semantic Data Model:
              </Typography>
              <Typography>{semanticModels[0].name}</Typography>
            </Box>
          ) : (
            <Box display="flex" flexDirection="column" gap="$4">
              <Typography variant="body-medium" fontWeight="medium">
                Select Semantic Data Model:
              </Typography>
              <Select
                value={selectedModelId}
                onChange={(value) => handleModelSelect(value as string)}
                items={semanticModels.map((model) => ({
                  value: model.id,
                  label: model.name,
                  description: model.description,
                }))}
                aria-label="Select Semantic Data Model"
              />
            </Box>
          )}
        </Box>
      </Dialog.Content>
      <Dialog.Actions>
        <Button
          onClick={() => {
            if (selectedModelId) {
              handleModelSelect(selectedModelId);
            } else if (semanticModels.length === 1) {
              handleModelSelect(semanticModels[0].id);
            }
          }}
          disabled={!selectedModelId && semanticModels.length > 1}
        >
          Continue
        </Button>
        <Button variant="outline" onClick={handleClose}>
          Cancel
        </Button>
      </Dialog.Actions>
    </Dialog>
  );
};

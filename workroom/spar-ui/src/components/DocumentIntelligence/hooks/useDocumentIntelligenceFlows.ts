import { useCallback, useRef } from 'react';
import { FlowType } from '../types';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import type {
  ValidationRule,
  DataModelPayload,
  DocumentLayoutPayload,
  DataModel,
} from '../store/useDocumentIntelligenceStore';
import {
  useParseDocumentMutation,
  useGenerateDataModelMutation,
  useCreateDataModelMutation,
  useGenerateLayoutMutation,
  useExtractDocumentMutation,
  useGenerateDataModelDescriptionMutation,
  useIngestDocumentMutation,
  useGenerateQualityChecksMutation,
  useExecuteQualityChecksMutation,
  useGenerateExtractionSchemaMutation,
  useGetDataModelsMutation,
} from '../../../queries/documentIntelligence';
import {
  convertParseResultToFields,
  convertParseResultToTables,
  toSnakeCase,
} from '../utils/dataTransformations';

// Helper function to parse data model fields from string to objects
const parseDataModelFields = (dataModel: DataModel): DataModelPayload => ({
  ...dataModel,
  model_schema: typeof dataModel.model_schema === 'string'
    ? JSON.parse(dataModel.model_schema)
    : dataModel.model_schema,
  views: typeof dataModel.views === 'string'
    ? JSON.parse(dataModel.views)
    : dataModel.views,
  quality_checks: typeof dataModel.quality_checks === 'string'
    ? JSON.parse(dataModel.quality_checks)
    : dataModel.quality_checks
});

// Hook for document layout flow orchestration
export const useDocumentLayoutFlow = () => {
  const parseDocumentMutation = useParseDocumentMutation({});
  const generateDataModelMutation = useGenerateDataModelMutation({});
  const createDataModelMutation = useCreateDataModelMutation({});
  const generateLayoutMutation = useGenerateLayoutMutation({});
  const extractDocumentMutation = useExtractDocumentMutation({});
  const generateDataModelDescriptionMutation = useGenerateDataModelDescriptionMutation({});
  const ingestDocumentMutation = useIngestDocumentMutation({});
  const generateExtractionSchemaMutation = useGenerateExtractionSchemaMutation({})

  const {
    setParseData,
    setExtractedData,
    setLayoutFields,
    setLayoutTables,
    setSelectedFields,
    setSelectedTableColumns,
    setProcessingState,
    setProcessingError,
    clearProcessingState,
    setCurrentFlowType,
  } = useDocumentIntelligenceStore();

  const executeDocumentLayoutFlow = useCallback(async ({
    fileRef,
    threadId,
    agentId,
    dataModelName,
    flowType,
  }: {
    fileRef: File;
    threadId: string;
    agentId: string;
    dataModelName?: string;
    flowType: FlowType;
  }) => {
    try {
      setCurrentFlowType(flowType);
      setProcessingState(true, 'Starting document processing...', null);

      // Step 1: Parse document
      setProcessingState(true, 'Parsing document...', null);
      const parseResult = await parseDocumentMutation.mutateAsync({
        threadId,
        formData: fileRef,
      });

      setParseData(parseResult);

      // Step 2: Handle different flow types
      let finalDocumentLayout: DocumentLayoutPayload | undefined;

      if (flowType === 'create_data_model_plus_new_layout') {
        // Generate extraction schema without creating the data model
        setProcessingState(true, 'Generating extraction schema...', null);

        // Call the generateExtractionSchema endpoint to get the actual schema
        const schemaResult = await generateExtractionSchemaMutation.mutateAsync({
          threadId,
          agentId,
          formData: fileRef,
        });

        const { schema } = schemaResult;

        // Clear processing state after successful schema generation
        setProcessingState(false, '', null);

        // Convert parsed data to fields and tables for UI display
        const fields = convertParseResultToFields(parseResult);
        const tables = convertParseResultToTables(parseResult);

        finalDocumentLayout = {
          name: 'default',
          extraction_schema: {
            type: 'object',
            properties: schema,
            ...schema
          }
        };

        // Auto-select all fields and table columns
        const selectedFields = fields.map((_, index) => index);
        const selectedTableColumns: Record<string, number[]> = {};
        tables.forEach((table) => {
          const columnCount = Object.keys(table.columnsMeta || {}).length;
          selectedTableColumns[table.name] = Array.from({ length: columnCount }, (_, index) => index);
        });

        setLayoutFields(fields);
        setLayoutTables(tables);
        // Use setTimeout to ensure fields are set before selection
        setTimeout(() => {
          setSelectedFields(selectedFields);
          setSelectedTableColumns(selectedTableColumns);
        }, 0);

      } else if (flowType === 'create_doc_layout_from_existing_data_model') {
        if (!dataModelName) {
          throw new Error('Data model name is required');
        }

        // Load existing data model
        setProcessingState(true, 'Loading data model...', null);
        // Note: This would need to be implemented with a query hook
        // const dataModelQuery = useGetDataModelQuery({ modelName: dataModelName });

        // Generate layout
        setProcessingState(true, 'Generating document layout...', null);
        const layoutResult = await generateLayoutMutation.mutateAsync({
          dataModelName,
          threadId,
          agentId,
          formData: fileRef,
        });

        finalDocumentLayout = layoutResult.layout;

      } else if (flowType === 'parse_current_document') {
        // Parse the document and generate the extraction schema
        setProcessingState(true, 'Generating extraction schema...', null);

        // Call the generateExtractionSchema endpoint to get the actual schema
        const schemaResult = await generateExtractionSchemaMutation.mutateAsync({
          threadId,
          agentId,
          formData: fileRef,
        });


        // Extract the schema from the response
        const schema = schemaResult.schema || schemaResult;

        finalDocumentLayout = {
          extraction_schema: {
            type: 'object',
            properties: schema,
            ...schema
          }
        };

        // Don't auto-select fields for parse flow (read-only mode)
        setLayoutFields([]);
        setLayoutTables([]);
        setSelectedFields([]);
        setSelectedTableColumns({});
      }

      // Step 3: Extract data if we have a layout (ALL flows do this step)
      if (finalDocumentLayout) {

        setProcessingState(true, 'Extracting data...', null);

        const extractedData = await extractDocumentMutation.mutateAsync({
          threadId,
          fileName: fileRef.name,
          dataModelName,
          documentLayout: finalDocumentLayout,
          generateCitations: true,
        });


        setExtractedData(extractedData);

        // Convert extracted data to fields and tables for display
        const extractedFields = convertParseResultToFields(extractedData);
        const extractedTables = convertParseResultToTables(extractedData);

        // Update fields and tables with extracted data
        setLayoutFields(extractedFields);
        setLayoutTables(extractedTables);
      }

      setProcessingState(false, '', null);
      return { success: true };

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to execute document layout flow';
      setProcessingError(errorMessage);
      setProcessingState(false, '', errorMessage);
      throw error;
    }
  }, [
    parseDocumentMutation,
    generateDataModelMutation,
    createDataModelMutation,
    generateLayoutMutation,
    extractDocumentMutation,
    generateDataModelDescriptionMutation,
    ingestDocumentMutation,
    generateExtractionSchemaMutation,
    setParseData,
    setExtractedData,
    setLayoutFields,
    setLayoutTables,
    setSelectedFields,
    setSelectedTableColumns,
    setProcessingState,
    setProcessingError,
    clearProcessingState,
    setCurrentFlowType,
  ]);

  return {
    executeDocumentLayoutFlow,
    isLoading: parseDocumentMutation.isPending ||
                generateDataModelMutation.isPending ||
                createDataModelMutation.isPending ||
                generateLayoutMutation.isPending ||
                extractDocumentMutation.isPending ||
                generateDataModelDescriptionMutation.isPending ||
                ingestDocumentMutation.isPending,
    error: parseDocumentMutation.error ||
           generateDataModelMutation.error ||
           createDataModelMutation.error ||
           generateLayoutMutation.error ||
           extractDocumentMutation.error ||
           generateDataModelDescriptionMutation.error ||
           ingestDocumentMutation.error,
  };
};

// Hook for data model flow orchestration
export const useDataModelFlow = () => {
  const generateDataModelMutation = useGenerateDataModelMutation({});
  const createDataModelMutation = useCreateDataModelMutation({});
  const generateDataModelDescriptionMutation = useGenerateDataModelDescriptionMutation({});

  const {
    setProcessingState,
    setProcessingError,
    clearProcessingState,
    setDataModel,
  } = useDocumentIntelligenceStore();

  const executeDataModelFlow = useCallback(async ({
    fileRef,
    threadId,
    agentId,
    dataModelName,
    dataModelDescription,
  }: {
    fileRef: File;
    threadId: string;
    agentId: string;
    dataModelName?: string;
    dataModelDescription?: string;
  }) => {
    try {
      setProcessingState(true, 'Generating data model...', null);

      // Step 1: Generate data model
      const dataModelResult = await generateDataModelMutation.mutateAsync({
        threadId,
        agentId,
        formData: fileRef,
      });

      // Step 2: Create data model
      setProcessingState(true, 'Creating data model...', null);
      const createdModel = await createDataModelMutation.mutateAsync({
        agentId,
        threadId,
        dataModel: {
          name: dataModelName || `data_model_${Date.now()}`,
          description: dataModelDescription || `Auto-generated data model for ${fileRef.name}`,
          model_schema: dataModelResult.model_schema,
        },
      });

      // Save the created data model to the store
      // Parse the model_schema string to object and views string to array
      const parsedDataModel = parseDataModelFields(createdModel.data_model);
      setDataModel(parsedDataModel);

      setProcessingState(false, '', null);
      return { success: true, dataModel: createdModel.data_model };

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to execute data model flow';
      setProcessingError(errorMessage);
      setProcessingState(false, '', errorMessage);
      throw error;
    }
  }, [
    generateDataModelMutation,
    createDataModelMutation,
    generateDataModelDescriptionMutation,
    setProcessingState,
    setProcessingError,
    clearProcessingState,
  ]);

  return {
    executeDataModelFlow,
    isLoading: generateDataModelMutation.isPending ||
                createDataModelMutation.isPending ||
                generateDataModelDescriptionMutation.isPending,
    error: generateDataModelMutation.error ||
           createDataModelMutation.error ||
           generateDataModelDescriptionMutation.error,
  };
};

// Hook for data quality flow orchestration
export const useDataQualityFlow = () => {
  const generateQualityChecksMutation = useGenerateQualityChecksMutation({});
  const executeQualityChecksMutation = useExecuteQualityChecksMutation({});

  const {
    setDataQualityChecks,
    setDataQualityChecksError,
    setQualityCheckResult,
    setProcessingState,
    setProcessingError,
  } = useDocumentIntelligenceStore();

  const executeDataQualityFlow = useCallback(async ({
    agentId,
    dataModelName,
    threadId,
    description,
    limit = 3,
  }: {
    agentId: string;
    dataModelName: string;
    threadId?: string;
    description?: string;
    limit?: number;
  }) => {
    try {
      setProcessingState(true, 'Generating data quality checks...', null);

      // Generate quality checks
      const qualityChecksResult = await generateQualityChecksMutation.mutateAsync({
        agentId,
        dataModelName,
        threadId,
        description,
        limit,
      });

      // Transform API response to match QualityCheck type
      const transformedChecks = qualityChecksResult.quality_checks.map((check, index: number) => ({
        id: `quality_check_${index}`,
        name: check.rule_name || `Quality Check ${index + 1}`,
        type: 'validation',
        ...check, // Include all properties from ValidationRule
      }));

      setDataQualityChecks(transformedChecks);
      setProcessingState(false, '', null);

      return { success: true, qualityChecks: qualityChecksResult.quality_checks };

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to execute data quality flow';
      setDataQualityChecksError(errorMessage);
      setProcessingError(errorMessage);
      setProcessingState(false, '', errorMessage);
      throw error;
    }
  }, [
    generateQualityChecksMutation,
    executeQualityChecksMutation,
    setDataQualityChecks,
    setDataQualityChecksError,
    setQualityCheckResult,
    setProcessingState,
    setProcessingError,
  ]);

  const executeQualityChecks = useCallback(async ({
    qualityChecks,
    documentId,
  }: {
    qualityChecks: ValidationRule[];
    documentId: string;
  }) => {
    try {
      const results = await executeQualityChecksMutation.mutateAsync({
        qualityChecks,
        documentId,
      });

      // Update results in store
      results.results?.forEach((result) => {
        setQualityCheckResult(result.rule_name, {
          passed: result.status === 'passed',
          message: result.error_message || result.description || 'Check completed',
          details: result.context || {},
        });
      });

      return { success: true, results: results.results };

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to execute quality checks';
      setProcessingError(errorMessage);
      throw error;
    }
  }, [
    executeQualityChecksMutation,
    setQualityCheckResult,
    setProcessingError,
  ]);

  return {
    executeDataQualityFlow,
    executeQualityChecks,
    isLoading: generateQualityChecksMutation.isPending,
    error: generateQualityChecksMutation.error || executeQualityChecksMutation.error,
  };
};

// Hook for document ingestion
export const useDocumentIngestion = () => {
  const ingestDocumentMutation = useIngestDocumentMutation({});

  const {
    setIngestedDocument,
    setProcessingState,
    setProcessingError,
  } = useDocumentIntelligenceStore();

  const ingestDocument = useCallback(async ({
    fileRef,
    threadId,
    agentId,
    dataModelName,
    layoutName,
  }: {
    fileRef: File;
    threadId: string;
    agentId: string;
    dataModelName: string;
    layoutName: string;
  }) => {
    try {
      setProcessingState(true, 'Ingesting document...', null);

      const result = await ingestDocumentMutation.mutateAsync({
        threadId,
        dataModelName,
        layoutName,
        agentId,
        formData: fileRef,
      });

      setIngestedDocument(result);
      setProcessingState(false, '', null);

      return { success: true, ingestedDocument: result };

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to ingest document';
      setProcessingError(errorMessage);
      setProcessingState(false, '', errorMessage);
      throw error;
    }
  }, [
    ingestDocumentMutation,
    setIngestedDocument,
    setProcessingState,
    setProcessingError,
  ]);

  return {
    ingestDocument,
    isLoading: ingestDocumentMutation.isPending,
    error: ingestDocumentMutation.error,
  };
};

// Hook for generating data model descriptions
export const useDataModelDescriptionGeneration = () => {
  const generateDataModelDescriptionMutation = useGenerateDataModelDescriptionMutation({});
  const mutationRef = useRef(generateDataModelDescriptionMutation);
  mutationRef.current = generateDataModelDescriptionMutation;

  const {
    setIsGeneratingDescription,
    setProcessingError,
  } = useDocumentIntelligenceStore();

  const generateDataModelDescription = useCallback(async ({
    threadId,
    agentId,
    fileRef,
  }: {
    threadId: string;
    agentId: string;
    fileRef: string;
  }) => {
    try {
      setIsGeneratingDescription(true);
      setProcessingError(null);

      const result = await mutationRef.current.mutateAsync({
        threadId,
        agentId,
        fileRef,
      });

      setIsGeneratingDescription(false);
      return result.description || 'Generated description';
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to generate description';
      setProcessingError(errorMessage);
      setIsGeneratingDescription(false);
      throw error;
    }
  }, [
    setIsGeneratingDescription,
    setProcessingError,
  ]);

  return {
    generateDataModelDescription,
    isLoading: generateDataModelDescriptionMutation.isPending,
    error: generateDataModelDescriptionMutation.error,
  };
};

// Hook for handling data model name dialog save
export const useDataModelNameDialogSave = () => {
  const generateDataModelMutation = useGenerateDataModelMutation({});
  const createDataModelMutation = useCreateDataModelMutation({});
  const ingestDocumentMutation = useIngestDocumentMutation({});
  const getDataModelsMutation = useGetDataModelsMutation({});

  const {
    setProcessingState,
    setProcessingError,
    closeDataModelNameDialog,
    setDataModel,
    setIngestedDocument,
  } = useDocumentIntelligenceStore();

  const checkModelExists = useCallback(async (name: string) => {
    const snakeCaseName = toSnakeCase(name);
    setProcessingState(true, 'Checking for existing models...', null);
    const existingModels = await getDataModelsMutation.mutateAsync({});

    if (existingModels && Array.isArray(existingModels) && existingModels.length > 0) {
      const modelExists = existingModels.some((model: DataModelPayload) => model.name === snakeCaseName);
      if (modelExists) {
        setProcessingError(`"${name}" already exists. Please choose a different name.`);
        setProcessingState(false, '', `"${name}" already exists. Please choose a different name.`);
        return true;
      }
    }
    return false;
  }, [getDataModelsMutation, setProcessingState, setProcessingError]);

  const createDataModel = useCallback(async (name: string, description: string, fileRef: File, threadId: string, agentId: string) => {
    setProcessingState(true, 'Creating data model...', null);

    const generatedModel = await generateDataModelMutation.mutateAsync({
      threadId,
      agentId,
      formData: fileRef,
    });

    const schema = generatedModel.model_schema;
    if (!schema) {
      throw new Error('Failed to generate data model schema');
    }

    const dataModelResult = await createDataModelMutation.mutateAsync({
      agentId,
      threadId,
      dataModel: {
        name: name.trim(),
        description: description.trim(),
        model_schema: schema,
      },
    });

    // Parse the model_schema string to object and views string to array
    const parsedDataModel = parseDataModelFields(dataModelResult.data_model);
    setDataModel(parsedDataModel);
    return dataModelResult;
  }, [generateDataModelMutation, createDataModelMutation, setProcessingState, setDataModel]);

  const ingestDocument = useCallback(async (name: string, fileRef: File, threadId: string, agentId: string) => {
    const ingestResult = await ingestDocumentMutation.mutateAsync({
      threadId,
      dataModelName: name.trim(),
      layoutName: 'default',
      agentId,
      formData: fileRef,
    });
    setIngestedDocument(ingestResult);
    return ingestResult;
  }, [ingestDocumentMutation, setIngestedDocument]);

  const handleDataModelNameSave = useCallback(async ({
    name,
    description,
    fileRef,
    threadId,
    agentId,
    onSuccess,
  }: {
    name: string;
    description: string;
    fileRef: File;
    threadId: string;
    agentId: string;
    onSuccess?: () => void;
  }) => {
    try {
      if (await checkModelExists(name)) return;

      await createDataModel(name, description, fileRef, threadId, agentId);

      // If we get here, data model was created successfully
      try {
        await ingestDocument(name, fileRef, threadId, agentId);
        setProcessingState(false, '', null);
        closeDataModelNameDialog();
        onSuccess?.();
      } catch (ingestError) {
        const errorMessage = ingestError instanceof Error ? ingestError.message : 'Failed to ingest document';
        setProcessingError(`Data model created successfully, but document ingestion failed: ${errorMessage}`);
        setProcessingState(false, '', `Data model created successfully, but document ingestion failed: ${errorMessage}`);
        closeDataModelNameDialog();
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to save data model';
      setProcessingError(errorMessage);
      setProcessingState(false, '', errorMessage);
      throw error;
    }
  }, [
    checkModelExists,
    createDataModel,
    ingestDocument,
    setProcessingState,
    setProcessingError,
    closeDataModelNameDialog,
  ]);

  return {
    handleDataModelNameSave,
    isLoading: generateDataModelMutation.isPending || createDataModelMutation.isPending || ingestDocumentMutation.isPending || getDataModelsMutation.isPending,
    error: generateDataModelMutation.error || createDataModelMutation.error || ingestDocumentMutation.error || getDataModelsMutation.error,
  };
};

// Hook for handling flow transitions
export const useDocumentIntelligenceFlowTransitions = () => {
  const {
    layoutFields,
    layoutTables,
    setSelectedFields,
    setSelectedTableColumns,
    setCurrentFlowType,
  } = useDocumentIntelligenceStore();

  const handleParseToCreateDataModelTransition = useCallback(async () => {
    try {
      setCurrentFlowType('create_data_model_plus_new_layout');

      // Auto-select all fields and table columns when transitioning to create_data_model_plus_new_layout
      if (layoutFields && layoutFields.length > 0) {
        const allFieldIndices = layoutFields.map((_, index) => index);
        setSelectedFields(allFieldIndices);
      }

      if (layoutTables && layoutTables.length > 0) {
        const allTableColumnSelections: Record<string, number[]> = {};
        layoutTables.forEach((table) => {
          const columnCount = Object.keys(table.columnsMeta || {}).length;
          allTableColumnSelections[table.name] = Array.from({ length: columnCount }, (_, index) => index);
        });
        setSelectedTableColumns(allTableColumnSelections);
      }

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to transition to create data model flow';
      throw new Error(errorMessage);
    }
  }, [
    layoutFields,
    layoutTables,
    setSelectedFields,
    setSelectedTableColumns,
    setCurrentFlowType,
  ]);

  const handleCreateDataModelPlusNewLayoutFlow = useCallback(async ({
    currentStep,
    goToNextStep,
    openDataModelNameDialog,
    commitLayout,
    commitDataModel,
    handleClose,
  }: {
    currentStep: string;
    goToNextStep: () => void;
    openDataModelNameDialog: () => void;
    commitLayout: () => Promise<void>;
    commitDataModel: (options: { agentId: string; threadId: string }) => Promise<void>;
    handleClose: () => void;
  }) => {
    try {
      if (currentStep === 'document_layout') {
        goToNextStep();
        return;
      }
      if (currentStep === 'data_model') {
        openDataModelNameDialog();
        return;
      }
      if (currentStep === 'data_quality') {
        // Commit the layout and data model to the database
        await commitLayout();
        await commitDataModel({ agentId: '', threadId: '' });
        handleClose();
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to execute create data model plus new layout flow';
      throw new Error(errorMessage);
    }
  }, []);

  const handleCreateDocLayoutFromExistingDataModelFlow = useCallback(async ({
    currentStep,
    dataModelName,
    documentLayout,
    fileRef,
    threadId,
    agentId,
    commitLayout,
    ingestDocument,
    commitDataModel,
    goToNextStep,
    handleClose,
  }: {
    currentStep: string;
    dataModelName?: string;
    documentLayout?: DocumentLayoutPayload;
    fileRef: File;
    threadId: string;
    agentId: string;
    commitLayout: (options: { action: string }) => Promise<void>;
    ingestDocument: (options: { fileRef: File; threadId: string; agentId: string }) => Promise<void>;
    commitDataModel: () => Promise<void>;
    goToNextStep: () => void;
    handleClose: () => void;
  }) => {
    try {
      if (!dataModelName) {
        throw new Error('Data model name is required');
      }
      if (!documentLayout) {
        throw new Error('Document layout is required');
      }

      if (currentStep === 'document_layout') {
        await commitLayout({
          action: 'create',
        });
        await ingestDocument({fileRef, threadId, agentId});
        goToNextStep();
        return;
      }
      if (currentStep === 'data_quality') {
        await commitLayout({
          action: 'create',
        });
        await commitDataModel();
        handleClose();
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to execute create doc layout from existing data model flow';
      throw new Error(errorMessage);
    }
  }, []);

  return {
    handleParseToCreateDataModelTransition,
    handleCreateDataModelPlusNewLayoutFlow,
    handleCreateDocLayoutFromExistingDataModelFlow,
  };
};

// Export new hooks
export { useDocumentCommits } from './useDocumentCommits';
export { useStepNavigation } from './useStepNavigation';
export { useResizablePanel } from './useResizablePanel';
export { useFlowHandlers } from './useFlowHandlers';

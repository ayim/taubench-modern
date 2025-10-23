import { useCallback } from 'react';
import { useSnackbar } from '@sema4ai/components';
import { useExtractDocumentMutation } from '../../../queries/documentIntelligence';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import { convertParseResultToFields, convertParseResultToTables, convertUIStateToDocumentLayoutPayload } from '../utils/dataTransformations';
import { DocumentData } from '../types';
import type { ExtractionSchemaPayload } from '../store/useDocumentIntelligenceStore';

export const useRetryExtract = () => {
  const extractDocumentMutation = useExtractDocumentMutation({});
  const { addSnackbar } = useSnackbar();

  const {
    layoutFields,
    layoutTables,
    documentLayout,
    originalGeneratedSchema,
    setExtractedData,
    setLayoutFields,
    setLayoutTables,
    setProcessingState,
    setProcessingError,
    clearProcessingState,
    setShowingParseBoxes,
  } = useDocumentIntelligenceStore();

  const retryExtract = useCallback(async (documentData: DocumentData) => {
    try {
      setProcessingState(true, 'Retrying extraction with updated schema...', null);

      // Convert current UI state to DocumentLayoutPayload using original schema as base
      const documentLayoutPayload = convertUIStateToDocumentLayoutPayload(
        layoutFields,
        layoutTables,
        documentLayout,
        originalGeneratedSchema as ExtractionSchemaPayload | null
      );

      // Call extract endpoint with updated schema
      const extractedData = await extractDocumentMutation.mutateAsync({
        threadId: documentData.threadId,
        fileName: documentData.fileRef.name,
        dataModelName: documentData.dataModelName,
        documentLayout: documentLayoutPayload,
        generateCitations: true,
      });

      // Update store with new extracted data
      setExtractedData(extractedData);

      // Hide parse boxes and show extract citations after retry extraction completes
      setShowingParseBoxes(false);

      // Convert extracted data to fields and tables for display
      const extractedFields = convertParseResultToFields(extractedData);
      const extractedTables = convertParseResultToTables(extractedData);

      // Update existing fields with new values while preserving IDs and other properties
      const updatedFields = layoutFields.map(existingField => {
        const extractedField = extractedFields.find(ef => ef.name === existingField.name);
        if (extractedField) {
          return {
            ...existingField,
            value: extractedField.value,
            // Update other properties that might have changed
            type: extractedField.type,
            required: extractedField.required,
            description: extractedField.description,
            citationId: extractedField.citationId,
          };
        }
        return existingField;
      });

      // Add any new fields that weren't in the original layout
      const newFields = extractedFields.filter(extractedField =>
        !layoutFields.some(existingField => existingField.name === extractedField.name)
      );

      // Update fields and tables with extracted data
      setLayoutFields([...updatedFields, ...newFields]);
      setLayoutTables(extractedTables);

      setProcessingState(false, '', null);
      addSnackbar({
        message: 'Document re-extracted successfully with updated schema!',
        variant: 'success'
      });

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to retry extraction';
      setProcessingError(errorMessage);
      setProcessingState(false, '', errorMessage);
      // Reset parse boxes state on error
      setShowingParseBoxes(false);
      addSnackbar({
        message: `Failed to retry extraction: ${errorMessage}`,
        variant: 'danger'
      });
      throw error;
    }
  }, [
    layoutFields,
    layoutTables,
    documentLayout,
    originalGeneratedSchema,
    extractDocumentMutation,
    setExtractedData,
    setLayoutFields,
    setLayoutTables,
    setProcessingState,
    setProcessingError,
    clearProcessingState,
    setShowingParseBoxes,
    addSnackbar,
  ]);

  return {
    retryExtract,
    isLoading: extractDocumentMutation.isPending,
  };
};

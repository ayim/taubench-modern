import { useCallback } from 'react';
import { useSnackbar } from '@sema4ai/components';
import { useExtractDocumentMutation } from '../../../queries/documentIntelligence';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import {
  convertParseResultToFields,
  convertParseResultToTables,
  convertUIStateToDocumentLayoutPayload,
} from '../utils/dataTransformations';
import { DocumentData } from '../types';

export const useRetryExtract = () => {
  const extractDocumentMutation = useExtractDocumentMutation({});
  const { addSnackbar } = useSnackbar();

  const layoutFields = useDocumentIntelligenceStore((state) => state.layoutFields);
  const layoutTables = useDocumentIntelligenceStore((state) => state.layoutTables);
  const documentLayout = useDocumentIntelligenceStore((state) => state.documentLayout);
  const originalGeneratedSchema = useDocumentIntelligenceStore((state) => state.originalGeneratedSchema);
  const setExtractedData = useDocumentIntelligenceStore((state) => state.setExtractedData);
  const setLayoutFields = useDocumentIntelligenceStore((state) => state.setLayoutFields);
  const setLayoutTables = useDocumentIntelligenceStore((state) => state.setLayoutTables);
  const setProcessingState = useDocumentIntelligenceStore((state) => state.setProcessingState);
  const setProcessingError = useDocumentIntelligenceStore((state) => state.setProcessingError);
  const clearProcessingState = useDocumentIntelligenceStore((state) => state.clearProcessingState);
  const setShowingParseBoxes = useDocumentIntelligenceStore((state) => state.setShowingParseBoxes);

  const retryExtract = useCallback(
    async (documentData: DocumentData) => {
      try {
        setProcessingState(true, 'Retrying extraction with updated schema...', null);

        // Convert current UI state to DocumentLayoutPayload using original schema as base
        const documentLayoutPayload = convertUIStateToDocumentLayoutPayload(
          layoutFields,
          layoutTables,
          documentLayout,
          originalGeneratedSchema,
        );

        const extractedData = await extractDocumentMutation.mutateAsync({
          threadId: documentData.threadId,
          fileName: documentData.fileRef.name,
          dataModelName: documentData.dataModelName,
          documentLayout: documentLayoutPayload,
          generateCitations: true,
        });

        setExtractedData(extractedData);
        setShowingParseBoxes(false);

        // Convert extracted data to fields and tables for display
        // Use the updated schema (documentLayoutPayload.extraction_schema) that was sent to backend
        // This preserves layout_description and other user modifications
        const updatedSchema = documentLayoutPayload.extraction_schema as typeof originalGeneratedSchema;
        const extractedFields = convertParseResultToFields(extractedData, updatedSchema);
        const extractedTables = convertParseResultToTables(extractedData, updatedSchema);

        // Update existing fields with new values while preserving IDs and other properties
        const updatedFields = layoutFields.map((existingField) => {
          const extractedField = extractedFields.find((ef) => ef.name === existingField.name);
          if (extractedField) {
            return {
              ...existingField,
              value: extractedField.value,
              description: existingField.description || extractedField.description,
              layout_description: existingField.layout_description || extractedField.layout_description,
              citationId: extractedField.citationId,
            };
          }
          return existingField;
        });

        // Add any new fields that weren't in the original layout
        const newFields = extractedFields.filter(
          (extractedField) => !layoutFields.some((existingField) => existingField.name === extractedField.name),
        );

        setLayoutFields([...updatedFields, ...newFields]);
        setLayoutTables(extractedTables);

        setProcessingState(false, '', null);
        addSnackbar({
          message: 'Document re-extracted successfully with updated schema!',
          variant: 'success',
        });

        return { success: true };
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to retry extraction';
        setProcessingError(errorMessage);
        setProcessingState(false, '', errorMessage);
        setShowingParseBoxes(false);
        addSnackbar({
          message: `Failed to retry extraction: ${errorMessage}`,
          variant: 'danger',
        });
        throw error;
      }
    },
    [
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
    ],
  );

  return {
    retryExtract,
    isLoading: extractDocumentMutation.isPending,
  };
};

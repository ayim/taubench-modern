import { useCallback } from 'react';
import { useSnackbar } from '@sema4ai/components';
import { useCreateDataModelMutation, useUpsertLayoutMutation } from '../../../queries/documentIntelligence';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import type { DocumentLayoutPayload } from '../store/useDocumentIntelligenceStore';

export const useDocumentCommits = () => {
  const { dataModel, documentLayout } = useDocumentIntelligenceStore();
  const { addSnackbar } = useSnackbar();

  const createDataModelMutation = useCreateDataModelMutation({});
  const upsertLayoutMutation = useUpsertLayoutMutation({});

  const commitLayout = useCallback(async () => {
    if (!dataModel) {
      throw new Error('Missing data model data');
    }

    try {
      // Create layout data from current state
      const layoutData: DocumentLayoutPayload = {
        name: 'default',
        extraction_schema: {
          type: 'object',
          properties: {},
          required: []
        },
        prompt: documentLayout?.prompt || '',
        data_model_name: dataModel.name,
      };

      await upsertLayoutMutation.mutateAsync({ layoutData });
      addSnackbar({ message: 'Document layout saved successfully' });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to save document layout';
      addSnackbar({ message: errorMessage });
      throw error;
    }
  }, [dataModel, documentLayout, addSnackbar, upsertLayoutMutation]);

  const commitDataModel = useCallback(async ({ agentId, threadId }: { agentId: string; threadId: string }) => {
    if (!dataModel) {
      throw new Error('No data model data found');
    }

    try {
      await createDataModelMutation.mutateAsync({
        agentId,
        threadId,
        dataModel,
      });
      addSnackbar({ message: 'Data model saved successfully' });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to save data model';
      addSnackbar({ message: errorMessage });
      throw error;
    }
  }, [dataModel, addSnackbar, createDataModelMutation]);

  return {
    commitLayout,
    commitDataModel,
  };
};

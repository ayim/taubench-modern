import { useCallback } from 'react';
import { useSnackbar } from '@sema4ai/components';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import {
  useDocumentIntelligenceFlowTransitions,
  useDocumentLayoutFlow,
  useDataModelFlow,
} from './useDocumentIntelligenceFlows';
import { useDocumentCommits } from './useDocumentCommits';
import { useIngestDocumentMutation } from '../../../queries/documentIntelligence';
import { DocumentData } from '../types';

export const useFlowHandlers = () => {
  const currentFlowType = useDocumentIntelligenceStore((state) => state.currentFlowType);
  const documentLayout = useDocumentIntelligenceStore((state) => state.documentLayout);
  const {
    handleParseToCreateDataModelTransition,
    handleCreateDataModelPlusNewLayoutFlow,
    handleCreateDocLayoutFromExistingDataModelFlow,
  } = useDocumentIntelligenceFlowTransitions();
  const { executeDocumentLayoutFlow } = useDocumentLayoutFlow();
  const { executeDataModelFlow } = useDataModelFlow();
  const { commitLayout, commitDataModel } = useDocumentCommits();
  const { addSnackbar } = useSnackbar();
  const ingestDocumentMutation = useIngestDocumentMutation({});

  const handleComplete = useCallback(
    async ({
      currentStep,
      goToNextStep,
      openDataModelNameDialog,
      onClose,
      documentData,
      isLastStep,
    }: {
      currentStep: string;
      goToNextStep: () => void;
      openDataModelNameDialog: () => void;
      onClose: () => void;
      documentData: DocumentData;
      isLastStep: boolean;
    }) => {
      try {
        if (currentFlowType === 'parse_current_document') {
          await handleParseToCreateDataModelTransition();
          return;
        }

        if (currentFlowType === 'create_data_model_plus_new_layout') {
          await handleCreateDataModelPlusNewLayoutFlow({
            currentStep,
            goToNextStep,
            openDataModelNameDialog,
            commitLayout,
            commitDataModel: () => commitDataModel({ agentId: documentData.agentId, threadId: documentData.threadId }),
            handleClose: onClose,
          });
          return;
        }

        // Handle create_doc_layout_from_existing_data_model flow
        if (currentFlowType === 'create_doc_layout_from_existing_data_model') {
          await handleCreateDocLayoutFromExistingDataModelFlow({
            currentStep,
            dataModelName: documentData.dataModelName,
            documentLayout: documentLayout || undefined,
            fileRef: documentData.fileRef,
            threadId: documentData.threadId,
            agentId: documentData.agentId,
            commitLayout: async () => {
              await commitLayout();
            },
            ingestDocument: async ({ fileRef, threadId, agentId }) => {
              try {
                await ingestDocumentMutation.mutateAsync({
                  threadId,
                  dataModelName: documentData.dataModelName || 'default',
                  layoutName: 'default',
                  agentId,
                  formData: fileRef,
                });
                addSnackbar({ message: 'Document ingested successfully' });
              } catch (error) {
                const errorMessage = error instanceof Error ? error.message : 'Failed to ingest document';
                addSnackbar({ message: errorMessage, variant: 'danger' });
                throw error;
              }
            },
            commitDataModel: async () => {
              await commitDataModel({ agentId: documentData.agentId, threadId: documentData.threadId });
            },
            goToNextStep,
            handleClose: onClose,
          });
          return;
        }

        if (isLastStep) {
          onClose();
        } else {
          goToNextStep();
        }
      } catch (error) {
        addSnackbar({
          message: `Error in handleComplete: ${error instanceof Error ? error.message : 'Error'}`,
          variant: 'danger',
        });
      }
    },
    [
      currentFlowType,
      handleParseToCreateDataModelTransition,
      handleCreateDataModelPlusNewLayoutFlow,
      handleCreateDocLayoutFromExistingDataModelFlow,
      commitLayout,
      commitDataModel,
    ],
  );

  const handleRetryDocumentLayoutFlow = useCallback(
    async (documentData: DocumentData) => {
      try {
        await executeDocumentLayoutFlow({
          fileRef: documentData.fileRef,
          threadId: documentData.threadId,
          agentId: documentData.agentId,
          dataModelName: documentData.dataModelName,
          flowType: currentFlowType || documentData.flowType,
        });
      } catch (error) {
        addSnackbar({
          message: `Failed to retry document layout flow: ${error instanceof Error ? error.message : 'Error'}`,
          variant: 'danger',
        });
      }
    },
    [executeDocumentLayoutFlow, currentFlowType],
  );

  const handleRetryDataModelFlow = useCallback(
    async (documentData: DocumentData) => {
      try {
        await executeDataModelFlow({
          fileRef: documentData.fileRef,
          threadId: documentData.threadId,
          agentId: documentData.agentId,
          dataModelName: documentData.dataModelName,
          dataModelDescription: undefined,
        });
      } catch (error) {
        addSnackbar({
          message: `Failed to retry data model flow: ${error instanceof Error ? error.message : 'Error'}`,
          variant: 'danger',
        });
      }
    },
    [executeDataModelFlow],
  );

  return {
    handleComplete,
    handleRetryDocumentLayoutFlow,
    handleRetryDataModelFlow,
  };
};

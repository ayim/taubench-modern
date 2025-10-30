import { FC, useCallback, useEffect, useState } from 'react';
import { Box, Dialog, Typography, Button } from '@sema4ai/components';

import { DocumentData } from '../types';
import { DocumentIntelligenceView } from './View';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import { useStepManagement } from '../hooks/useStepManagement';

interface DocumentIntelligenceDialogProps {
  isOpen: boolean;
  onClose: () => void;

  documentData: DocumentData;
}

export const DocumentIntelligenceDialog: FC<DocumentIntelligenceDialogProps> = ({ isOpen, onClose, documentData }) => {
  const { fileRef, flowType } = documentData;
  const setFileRef = useDocumentIntelligenceStore((state) => state.setFileRef);
  const reset = useDocumentIntelligenceStore((state) => state.reset);
  const currentFlowType = useDocumentIntelligenceStore((state) => state.currentFlowType);
  const cancelAllRequests = useDocumentIntelligenceStore((state) => state.cancelAllRequests);
  const activeRequests = useDocumentIntelligenceStore((state) => state.activeRequests);
  const { currentStep } = useStepManagement();
  const [openExitConfirmation, setOpenExitConfirmation] = useState(false);

  const handleCloseWithCancellation = useCallback(() => {
    if (activeRequests.size > 0) {
      cancelAllRequests();
    }
    reset(); // Clear all data immediately when closing
    onClose();
  }, [onClose, cancelAllRequests, activeRequests, reset]);

  const shouldShowConfirmation = useCallback(() => {
    // This means the user has completed the workflow and can close gracefully
    if (currentStep === 'data_quality') {
      return false;
    }

    return true;
  }, [currentStep]);

  const handleClose = useCallback(() => {
    if (shouldShowConfirmation()) {
      setOpenExitConfirmation(true);
    } else {
      handleCloseWithCancellation();
    }
  }, [shouldShowConfirmation, handleCloseWithCancellation]);

  useEffect(() => {
    if (isOpen && fileRef) {
      setFileRef(fileRef);
    } else if (!isOpen) {
      reset();
    }
  }, [isOpen, fileRef, setFileRef, reset]);

  const getDialogTitle = useCallback(() => {
    const effectiveFlowType = currentFlowType || flowType;
    switch (effectiveFlowType) {
      case 'create_data_model_plus_new_layout':
        return 'Create New Data Model';
      case 'parse_current_document':
        return 'Parse Document Results';
      case 'show_read_only_results':
        return 'Show Document Layout';
      case 'create_doc_layout_from_existing_data_model':
      default:
        effectiveFlowType satisfies 'create_doc_layout_from_existing_data_model';
        return 'Create New Document Layout';
    }
  }, [currentFlowType, flowType]);

  return (
    <>
      <Dialog open={isOpen} onClose={handleClose} size="full-screen">
      <Dialog.Header>
        <Box display="flex" alignItems="center" marginBottom="$16" gap="$8" flexShrink="0">
        <Typography fontSize="$20" fontWeight="bold">
          {getDialogTitle()}
        </Typography>
          {fileRef && (
            <Typography fontSize="$20" variant="body-large" fontWeight="bold" style={{ color: 'gray' }}>
              {fileRef.name}
            </Typography>
          )}
        </Box>
      </Dialog.Header>


      <Dialog.Content>
        <DocumentIntelligenceView documentData={documentData} onClose={handleClose} />
      </Dialog.Content>
    </Dialog>

    {/* EXIT CONFIRMATION DIALOG */}
    <Dialog open={openExitConfirmation} onClose={() => setOpenExitConfirmation(false)} size="medium">
      <Dialog.Header>
        <Dialog.Header.Title title="Are you sure?" />
      </Dialog.Header>
      <Dialog.Content>
        You are about to exit the Document Intelligence flow. This will discard all of the unsaved data and you will
        lose all progress.
      </Dialog.Content>
      <Dialog.Actions>
        <Button
          variant="primary"
          onClick={() => {
            setOpenExitConfirmation(false);
            reset(); // Clear all data immediately
            handleCloseWithCancellation();
          }}
        >
          Yes, exit
        </Button>
        <Button variant="secondary" onClick={() => setOpenExitConfirmation(false)}>
          No, continue
        </Button>
      </Dialog.Actions>
    </Dialog>
    </>
  );
};

import { Box, Button, useSnackbar } from '@sema4ai/components';
import { FC, useState } from 'react';
import { IconArrowLeft, IconArrowRight, IconRefresh } from '@sema4ai/icons';
import { FlowType, StepType, DocumentData } from '../types';
import { useRetryExtract } from '../hooks/useRetryExtract';

export interface StepFooterProps {
  flowType: FlowType | undefined | null;
  currentStep: StepType;
  isDisabled: boolean;
  goToPreviousStep: () => void;
  onComplete: () => Promise<void>;
  onCancel: () => void;
  documentData?: DocumentData;
}

export const StepFooter: FC<StepFooterProps> = ({
  flowType,
  currentStep,
  isDisabled,
  goToPreviousStep,
  onComplete,
  onCancel,
  documentData
}) => {
  const [isCompleting, setIsCompleting] = useState(false);
  const { addSnackbar } = useSnackbar();
  const { retryExtract, isLoading: isRetrying } = useRetryExtract();

  const handleComplete = async () => {
    setIsCompleting(true);
    try {
      await onComplete();
    } catch (e) {
      addSnackbar({ message: `Error completing step: ${e instanceof Error ? e.message : 'Error'}`, variant: 'danger' });
    } finally {
      setIsCompleting(false);
    }
  };

  const handleRetryExtract = async () => {
    if (!documentData) {
      addSnackbar({ message: 'Document data not available for retry', variant: 'danger' });
      return;
    }

    try {
      await retryExtract(documentData);
    } catch (error) {
      addSnackbar({ message: `Failed to retry extract: ${error instanceof Error ? error.message : 'Error'}`, variant: 'danger' });
    }
  };

  if (flowType === 'parse_current_document') {
    return (
      <Box display="flex" gap="$16">
        <Button variant="secondary" round onClick={onCancel}>
          Cancel
        </Button>
        <Box  style={{ backgroundColor: '#ffffff', borderRadius: '2.5rem' }}>
            <Button
              variant="ghost"
              round
              onClick={handleRetryExtract}
              disabled={isDisabled || isRetrying}
              icon={IconRefresh}
              loading={isRetrying}
            >
              Retry Extract
            </Button>
        </Box>
        <Button
          variant="primary"
          round
          onClick={handleComplete}
          disabled={isDisabled}
          iconAfter={IconArrowRight}
          loading={isCompleting}
        >
          Create a Data Model
        </Button>
      </Box>
    );
  }

  if (currentStep === 'data_quality') {
    return (
      <Box display="flex" gap="$16">
        <Button
          variant="primary"
          round
          onClick={handleComplete}
          iconAfter={IconArrowRight}
          disabled={isDisabled}
          loading={isCompleting}
        >
          Create
        </Button>
      </Box>
    );
  }

  if (currentStep === 'data_model') {
    return (
      <Box display="flex" gap="$16">
        <Button disabled={isDisabled} variant="secondary" icon={IconArrowLeft} round onClick={goToPreviousStep}>
          Back
        </Button>
        <Button disabled={isDisabled} variant="primary" round iconAfter={IconArrowRight} onClick={handleComplete}>
          Next
        </Button>
      </Box>
    );
  }

  // Default case (document_layout)
  return (
    <Box display="flex" gap="$16">
      <Button variant="secondary" round onClick={onCancel}>
        Cancel
      </Button>
      <Button disabled={isDisabled} variant="primary" round iconAfter={IconArrowRight} onClick={handleComplete}>
        Next
      </Button>
    </Box>
  );
};

import { Box, Button, useSnackbar } from '@sema4ai/components';
import { FC, useState } from 'react';
import { IconArrowLeft, IconArrowRight } from '@sema4ai/icons';
import { FlowType, StepType } from '../types';

export interface StepFooterProps {
  flowType: FlowType | undefined | null;
  currentStep: StepType;
  isDisabled: boolean;
  goToPreviousStep: () => void;
  onComplete: () => Promise<void>;
  onCancel: () => void;
}

export const StepFooter: FC<StepFooterProps> = ({
  flowType,
  currentStep,
  isDisabled,
  goToPreviousStep,
  onComplete,
  onCancel
}) => {
  const [isCompleting, setIsCompleting] = useState(false);
  const { addSnackbar } = useSnackbar();
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

  if (flowType === 'parse_current_document') {
    return (
      <Box display="flex" gap="$16">
        <Button variant="secondary" round onClick={onCancel}>
          Cancel
        </Button>
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

import { Box, Button, useSnackbar, Tooltip } from '@sema4ai/components';
import { FC, useState } from 'react';
import { IconArrowLeft, IconArrowRight, IconRefresh, IconStatusEnabled, IconStatusIdle } from '@sema4ai/icons';
import { FlowType, StepType } from '../types';

export interface StepFooterProps {
  flowType: FlowType | undefined | null;
  currentStep: StepType;
  isDisabled: boolean;
  goToPreviousStep: () => void;
  onComplete: () => Promise<void>;
  onCancel: () => void;
  schemaModified?: boolean;
  handleRerunExtractClick?: () => Promise<void>;
  isReRunning?: boolean;
}

export const StepFooter: FC<StepFooterProps> = ({
  flowType,
  currentStep,
  isDisabled,
  goToPreviousStep,
  onComplete,
  onCancel,
  schemaModified,
  handleRerunExtractClick,
  isReRunning,
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
    <Box display="flex" gap="$16" alignItems="center">
      {/* Status Indicator */}
      <Tooltip text={schemaModified ? 'Configuration changes made. Click Re-Run Extract to update extraction.' : 'Configuration is up to date'}>
        {schemaModified ? <IconStatusIdle color="background.notification" size={27} /> : <IconStatusEnabled color="content.success" size={27} />}
      </Tooltip>

      <Button variant="secondary" round onClick={onCancel}>
        Cancel
      </Button>

      {/* Re-Run Extract button */}
      {schemaModified && (
        <Button
          variant="outline"
          round
          onClick={handleRerunExtractClick}
          disabled={isDisabled || isReRunning || !handleRerunExtractClick}
          icon={IconRefresh}
          loading={isReRunning}
        >
          Re-Run Extract
        </Button>
      )}

      <Button disabled={isDisabled} variant="primary" round iconAfter={IconArrowRight} onClick={handleComplete} loading={isCompleting}>
        Next
      </Button>
    </Box>
  );
};

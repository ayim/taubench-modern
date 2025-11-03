import { FC, useMemo } from 'react';
import { Box, EmptyState, Typography } from '@sema4ai/components';
import { IconCheckCircle, IconLoading, IconAlertCircle } from '@sema4ai/icons';
import { Illustration } from '../../../Illustration';

interface ProcessingLoadingStateProps {
  processingStep?: string;
  title?: string;
}

export const ProcessingLoadingState: FC<ProcessingLoadingStateProps> = ({
  processingStep,
  title = 'Creating Data Model',
}) => {
  // Determine which step we're on based on processing step text
  const stepText = processingStep || 'Processing document...';
  const currentStep = stepText.toLowerCase();

  const getActiveStep = () => {
    // For creating data model, always show as active (single step)
    if (currentStep.includes('creating data model')) {
      return 0;
    }
    // For quality checks, always show as active (single step)
    if (currentStep.includes('quality checks')) {
      return 0;
    }
    // For custom schema import, always show as active (single step)
    if (currentStep.includes('custom schema')) {
      return 0;
    }
    // For re-extraction with updated schema, show schema generation step
    if (currentStep.includes('re-extract') && currentStep.includes('updated')) {
      return 0; // Schema generation step (no reading step for re-extraction)
    }
    if (currentStep.includes('parsing') || currentStep.includes('reading') || currentStep.includes('import')) {
      return 0;
    }
    if (currentStep.includes('model') || currentStep.includes('schema') || currentStep.includes('generate')) {
      return 1;
    }
    if (currentStep.includes('extract')) {
      return 2;
    }
    return 0;
  };

  const activeStep = useMemo(() => getActiveStep(), [currentStep]);

  const getStepStatus = (index: number) => {
    if (index < activeStep) return 'completed';
    if (index === activeStep) return 'loading';
    return 'pending';
  };

  const getStepLabels = () => {
    // Special case for creating data model - single step process
    if (currentStep.includes('creating data model')) {
      return [{ id: 'create-model', label: 'Creating data model' }];
    }

    // Special case for quality checks - single step process
    if (currentStep.includes('quality checks')) {
      return [{ id: 'quality-checks', label: 'Generating quality checks' }];
    }

    // Special case for importing custom schema - single step process
    if (currentStep.includes('custom schema')) {
      return [{ id: 'import-extract', label: 'Importing & Extracting with Custom Schema' }];
    }

    // Special case for re-extraction with updated schema - skip reading step
    if (currentStep.includes('re-extract') && currentStep.includes('updated')) {
      return [{ id: 'regenerate-schema', label: 'Re-Generating Extraction Schema' }];
    }

    let step0 = 'Reading document';
    if (currentStep.includes('import')) {
      step0 = 'Import';
    }

    let step1 = 'Generating extraction schema';
    if (currentStep.includes('model')) {
      step1 = 'Creating data model';
    } else if (currentStep.includes('generate') && !currentStep.includes('schema')) {
      step1 = 'Generating';
    }

    const step2 = 'Extracting data';

    return [
      { id: 'read-doc', label: step0 },
      { id: 'create-model', label: step1 },
      { id: 'extract-data', label: step2 },
    ];
  };

  const steps = getStepLabels();

  const getIcon = (status: string) => {
    if (status === 'completed') return IconCheckCircle;
    if (status === 'loading') return IconLoading;
    return IconAlertCircle;
  };

  const getColor = (status: string) => {
    if (status === 'completed') return 'content.success';
    if (status === 'loading') return 'content.primary';
    return 'content.subtle';
  };

  const titleText = useMemo(() => {
    if (currentStep.includes('creating data model')) {
      return 'Creating data model with your document schema';
    }

    // If re-extracting with updated schema
    if (currentStep.includes('re-extract') && currentStep.includes('updated')) {
      return 'Re-Generating Extraction Schema';
    }

    // If importing custom schema
    if (currentStep.includes('custom schema')) {
      return 'Importing Extraction Schema';
    }

    if (
      currentStep.includes('schema') ||
      currentStep.includes('extract') ||
      currentStep.includes('parsing') ||
      currentStep.includes('reading')
    ) {
      return 'Generating Extraction Schema';
    }

    if (currentStep.includes('quality checks')) {
      return 'Generating Quality Checks';
    }

    return title;
  }, [currentStep, title]);

  const descriptionText = useMemo(() => {
    if (currentStep.includes('creating data model')) {
      return '';
    }

    // For re-extraction with updated schema
    if (currentStep.includes('re-extract') && currentStep.includes('updated')) {
      return 'Re-extracting document data with latest changes';
    }

    // For custom schema import
    if (currentStep.includes('custom schema')) {
      return 'Re-extracting document data using your custom schema';
    }

    // For schema generation or extraction
    if (
      currentStep.includes('schema') ||
      currentStep.includes('extract') ||
      currentStep.includes('parse') ||
      currentStep.includes('reading')
    ) {
      return 'Your extraction will appear here once steps are complete';
    }

    if (currentStep.includes('quality checks')) {
      return 'Analyzing your extracted data to create validation rules';
    }

    // Default: show the processingStep text
    return processingStep || 'Processing document...';
  }, [currentStep, processingStep]);

  return (
    <Box style={{ height: '100%' }} display="flex" flexDirection="column" alignItems="center" justifyContent="center">
      <EmptyState
        illustration={<Illustration name="documents_processing" />}
        title={titleText}
        description={descriptionText}
        action={null}
      />
      <Box display="flex" alignItems="center" gap="$12" marginTop="-2rem" marginBottom="$0">
        {steps.map((step) => {
          const status = getStepStatus(steps.indexOf(step));
          const Icon = getIcon(status);
          const color = getColor(status);

          return (
            <Box key={step.id} display="flex" alignItems="center" gap="$8">
              <Icon color={color} />
              <Typography fontSize="$14" color={color}>
                {step.label}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

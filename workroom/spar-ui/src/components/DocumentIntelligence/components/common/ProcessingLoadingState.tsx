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
    // For custom schema import, always show as active (single step)
    if (currentStep.includes('custom schema')) {
      return 0;
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
    // Special case for importing custom schema - single step process
    if (currentStep.includes('custom schema')) {
      return [{ id: 'import-extract', label: 'Importing & Extracting with Custom Schema' }];
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
    // If importing custom schema
    if (currentStep.includes('custom schema')) {
      return 'Importing Extraction Schema';
    }

    // If generating extraction schema, extracting data, or parsing document
    if (
      currentStep.includes('schema') ||
      currentStep.includes('extract') ||
      currentStep.includes('parsing') ||
      currentStep.includes('reading')
    ) {
      return 'Generating Extraction Schema';
    }

    // If generating data quality checks
    if (currentStep.includes('quality checks')) {
      return 'Generating Quality Checks';
    }

    return title;
  }, [currentStep, title]);

  // Determine description text based on processing step
  const descriptionText = useMemo(() => {
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

    // For quality checks
    if (currentStep.includes('quality checks')) {
      return 'Your quality checks will appear here once they are complete';
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

import { FC } from 'react';
import { Box, EmptyState, Typography } from '@sema4ai/components';
import { IconLoading } from '@sema4ai/icons';

import { Illustration } from '~/components/Illustration';

interface Step {
  id: string;
  label: string;
  status: 'loading' | 'pending';
}

interface ProcessingLoadingStateProps {
  title?: string;
  description?: string;
  steps?: Step[];
  showSteps?: boolean;
}

export const ProcessingLoadingState: FC<ProcessingLoadingStateProps> = ({
  title = 'Parsing Document',
  description = 'Extracting text and structure from your document',
  steps = [{ id: 'parse', label: 'Parsing document', status: 'loading' }],
  showSteps = true,
}) => {
  const getIcon = () => {
    return IconLoading;
  };

  const getColor = (status: string) => {
    if (status === 'loading') return 'content.primary';
    return 'content.subtle';
  };

  return (
    <Box style={{ height: '100%' }} display="flex" flexDirection="column" alignItems="center" justifyContent="center">
      <EmptyState
        illustration={<Illustration name="documents_processing" />}
        title={title}
        description={description}
        action={null}
      />

      {/* Step Indicators */}
      {showSteps && steps.length > 0 && (
        <Box display="flex" alignItems="center" gap="$12" marginTop="-2rem" marginBottom="$0">
          {steps.map((step) => {
            const Icon = getIcon();
            const color = getColor(step.status);

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
      )}
    </Box>
  );
};

import { FC, useEffect, useState } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { IconSai } from '@sema4ai/icons/logos';
import { IconLoading, IconStatusCompleted, IconStatusTimeout } from '@sema4ai/icons';

const steps = [
  'Profiling tables and views',
  'Profiling columns',
  'Generating metadata',
  'Understanding relations',
  'Distilling business context',
];

export const Processing: FC = () => {
  const [currentStep, setCurrentStep] = useState(0);

  // TODO: Currently the process is "faked", this will be updated once streaming of the progress is implemented.
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev >= steps.length - 1) {
          clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" height="100%">
      <Box mb="$32">
        <IconSai size={48} />
      </Box>
      <Typography variant="display-small" mb="$8">
        SAI is working on your data model...
      </Typography>
      <Typography variant="body-medium-loose" color="content.subtle" textAlign="center" mb="$32">
        Data model creation may take a few minutes,
        <br />
        depending on the size of dataset and amount of columns you chose.
      </Typography>

      <Box display="flex" flexDirection="column" gap="$12">
        {steps.map((step, index) => (
          <Box key={step} display="flex" alignItems="center" gap="$8">
            {currentStep < index && <IconStatusTimeout />}
            {currentStep === index && <IconLoading />}
            {currentStep > index && <IconStatusCompleted color="content.success" />}
            <Typography variant="body-large">{step}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

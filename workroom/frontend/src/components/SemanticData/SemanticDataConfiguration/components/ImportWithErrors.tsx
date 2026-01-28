import { Box, Button, Typography } from '@sema4ai/components';
import { IconCheckCircle2 } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';

import { ConfigurationStep, ConfigurationStepView } from './form';

const SuccessIcon = styled(Box)`
  width: 48px;
  height: 48px;
  background-color: ${({ theme }) => theme.colors.background.notification.color};
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
`;

export const ImportWithErrors: ConfigurationStepView = ({ setActiveStep }) => {
  const onModelReview = () => {
    setActiveStep(ConfigurationStep.ModelEdition);
  };

  return (
    <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" height="100%" maxWidth={600}>
      <SuccessIcon mb="$32">
        <IconCheckCircle2 size={42} color="neutral" />
      </SuccessIcon>
      <Typography variant="display-small" mb="$8">
        Data Model Mismatch
      </Typography>
      <Typography variant="body-medium-loose" color="content.subtle" mb="$24" textAlign="center">
        Data Model imported with errors. It contains fields or tables that don’t exist or differ in type from those in
        the connected database.
      </Typography>
      <Button onClick={onModelReview} round>
        Review Model
      </Button>
    </Box>
  );
};

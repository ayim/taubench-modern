import { Box, Button, Typography } from '@sema4ai/components';
import { IconCheckCircle2 } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';

import { ConfigurationStep, ConfigurationStepView } from './form';
import { ModelScore } from './ModelEdition/components/ModelScore';

const SuccessIcon = styled(Box)`
  width: 48px;
  height: 48px;
  background-color: ${({ theme }) => theme.colors.content.success.color};
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
`;

export const SuccessView: ConfigurationStepView = ({ onClose, setActiveStep }) => {
  const onModelReview = () => {
    setActiveStep(ConfigurationStep.ModelEdition);
  };

  return (
    <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" height="100%" maxWidth={600}>
      <SuccessIcon mb="$32">
        <IconCheckCircle2 size={42} color="neutral" />
      </SuccessIcon>
      <Typography variant="display-small" mb="$8">
        Data Model Created
      </Typography>
      <Typography variant="body-medium-loose" color="content.subtle" mb="$24" textAlign="center">
        Call Center Data model is ready to be used with an agent! You can always come back to edit it for more
        precision.
      </Typography>
      <Box display="flex" width="100%" maxWidth={360} mb="$32">
        <ModelScore>
          <Button variant="secondary" onClick={onModelReview} round>
            Review
          </Button>
        </ModelScore>
      </Box>
      <Button onClick={onClose} round>
        Go to Agent
      </Button>
    </Box>
  );
};

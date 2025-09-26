import { FC } from 'react';
import { Box, Button, Typography, Tooltip, Divider } from '@sema4ai/components';
import { IconInformation, IconPlus, IconLightBulb } from '@sema4ai/icons';

export interface EvalHeaderProps {
  hasMessages: boolean;
  onAddEvaluation: () => void;
}

export const EvalHeader: FC<EvalHeaderProps> = ({
  hasMessages,
  onAddEvaluation,
}) => {
  return (
    <Box display="flex" flexDirection="column" gap="$8" flexShrink="0">
      <Box display="flex" alignItems="center" gap="$8">
        <Typography variant="display-small">Evaluations</Typography>
        <Tooltip text="Evaluations are used to test the performance of your agent.">
          <IconInformation size="48" color='content.subtle.light' />
        </Tooltip>
      </Box>
      
      <Typography variant="body-medium">
        All evaluations run will be shown here.
      </Typography>
      
      <Box display="flex" justifyContent="flex-start" paddingTop="$8" mb="$8">
        {!hasMessages ? (
          <Box 
            backgroundColor="yellow20" 
            padding="$20" 
            borderRadius="$12" 
            display="flex" 
            alignItems="center" 
            gap="$8"
          >
            <IconLightBulb size={24} />
            <Typography variant="body-medium">
              Talk to your agent to be able to add an evaluation.
            </Typography>
          </Box>
        ) : (
          <Button 
            variant="outline" 
            round 
            onClick={onAddEvaluation}
          >
            <IconPlus size="16" />
            Add Evaluation
          </Button>
        )}
      </Box>
      
      <Divider />
    </Box>
  );
};

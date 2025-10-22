import { FC } from 'react';
import { Box, Button, Typography, Tooltip, Divider } from '@sema4ai/components';
import { IconInformation, IconPlus, IconLightBulb, IconDownload } from '@sema4ai/icons';

export interface EvalHeaderProps {
  hasMessages: boolean;
  hasEvaluations: boolean;
  onAddEvaluation: () => void;
  onExportScenarios: () => void;
  isExporting: boolean;
}

export const EvalHeader: FC<EvalHeaderProps> = ({
  hasMessages,
  hasEvaluations,
  onAddEvaluation,
  onExportScenarios,
  isExporting,
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
        All evaluation runs will be shown here.
      </Typography>
      
      <Box display="flex" justifyContent="space-between" alignItems="center" paddingTop="$8" mb="$8" gap="$12" flexWrap="wrap">
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
          <Button variant="outline" round onClick={onAddEvaluation}>
            <IconPlus size="16" />
            Add Evaluation
          </Button>
        )}

        <Button
          variant="outline"
          round
          onClick={onExportScenarios}
          disabled={!hasEvaluations || isExporting}
          loading={isExporting}
        >
          <IconDownload size="16" />
          Export Scenarios
        </Button>
      </Box>
      
      <Divider />
    </Box>
  );
};

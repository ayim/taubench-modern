import { FC } from 'react';
import { Box, Button, EmptyState, Link } from '@sema4ai/components';
import { IconInformation, IconArrowUpRight } from '@sema4ai/icons';

export interface EvalEmptyStateProps {
  hasMessages: boolean;
  onAddEvaluation: () => void;
  onImportScenarios: () => void;
  isImporting: boolean;
}

export const EvalEmptyState: FC<EvalEmptyStateProps> = ({
  hasMessages,
  onAddEvaluation,
  onImportScenarios,
  isImporting,
}) => {
  return (
    <EmptyState
      title="Evaluations"
      description='All evaluation runs will be shown here. Create an Evaluation by clicking "Add Evaluation"'
      action={
        <Box display="flex" gap="$8" flexWrap="wrap">
          <Button 
            variant="primary" 
            round 
            onClick={onAddEvaluation} 
            disabled={!hasMessages}
          >
            Create Evaluation from Current Thread
          </Button>
          <Button
            variant="outline"
            round
            onClick={onImportScenarios}
            disabled={isImporting}
            loading={isImporting}
          >
            Import Evaluations
          </Button>
        </Box>
      }
      errorMessage={!hasMessages ? 'Talk to your agent to be able to add an evaluation.' : ''}
      secondaryAction={
        <Link
          icon={IconInformation}
          iconAfter={IconArrowUpRight}
          href="https://www.sema4.ai"
          target="_blank"
          rel="noopener"
          variant="primary"
          fontWeight="medium"
        >
          Learn More
        </Link>
      }
    />
  );
};

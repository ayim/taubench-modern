import { FC } from 'react';
import { Box, Button, EmptyState, Link } from '@sema4ai/components';
import { IconInformation, IconArrowUpRight } from '@sema4ai/icons';

import { useFeatureFlag } from '../../../../../hooks';
import { SparUIFeatureFlag } from '../../../../../api';

export interface EvalEmptyStateProps {
  hasMessages: boolean;
  onAddEvaluation: () => void;
  isFetchingSuggestion: boolean;
  onImportScenarios: () => void;
  isImporting: boolean;
}

export const EvalEmptyState: FC<EvalEmptyStateProps> = ({
  hasMessages,
  onAddEvaluation,
  isFetchingSuggestion,
  onImportScenarios,
  isImporting,
}) => {
  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const isImportEvaluationsDisabled = isImporting || !isChatInteractive;
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
            disabled={!hasMessages || isFetchingSuggestion}
            loading={isFetchingSuggestion}
          >
            {!isFetchingSuggestion && 'Create Evaluation from Current Thread'}
            {isFetchingSuggestion && 'Generating Evaluation...'}
          </Button>
          <Button
            variant="outline"
            round
            onClick={onImportScenarios}
            disabled={isImportEvaluationsDisabled}
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

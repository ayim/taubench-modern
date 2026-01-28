import { FC } from 'react';
import { Box, Button, EmptyState } from '@sema4ai/components';

import { Illustration } from '../../../../Illustration';
import { useFeatureFlag, FeatureFlag } from '../../../../../hooks';

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
  const { enabled: isChatInteractive } = useFeatureFlag(FeatureFlag.agentChatInput);

  const isImportEvaluationsDisabled = isImporting || !isChatInteractive;
  return (
    <EmptyState
      title="Evaluations"
      description='All evaluation runs will be shown here. Create an Evaluation by clicking "Add Evaluation"'
      action={
        <Box display="flex" gap="$8" flexWrap="wrap" justifyContent="center" alignItems="center" width="100%">
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
      illustration={<Illustration name="evals" />}
    />
  );
};

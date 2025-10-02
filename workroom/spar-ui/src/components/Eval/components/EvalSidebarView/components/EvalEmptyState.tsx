import { FC } from 'react';
import { Button, EmptyState, Link } from '@sema4ai/components';
import { IconInformation, IconArrowUpRight } from '@sema4ai/icons';

export interface EvalEmptyStateProps {
  hasMessages: boolean;
  onAddEvaluation: () => void;
}

export const EvalEmptyState: FC<EvalEmptyStateProps> = ({
  hasMessages,
  onAddEvaluation,
}) => {
  return (
    <EmptyState
      title="Evaluations"
      description='All evaluation runs will be shown here. Create an Evaluation by clicking "Add Evaluation"'
      action={
        <Button 
          variant="primary" 
          round 
          onClick={onAddEvaluation} 
          disabled={!hasMessages}
        >
          Create Evaluation from Current Thread
        </Button>
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

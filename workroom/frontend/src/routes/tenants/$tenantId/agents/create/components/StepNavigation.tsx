import { FC } from 'react';
import { Button } from '@sema4ai/components';

type Props = {
  isFinalStep: boolean;
  isPending: boolean;
  isFirstStep: boolean;
  onBack: () => void;
  onNext: () => void;
  onDeploy: () => void;
};

export const StepNavigation: FC<Props> = ({ isFinalStep, isPending, isFirstStep, onBack, onNext, onDeploy }) => {
  const handleCancel = () => {
    console.log('Cancel clicked');
  };

  return (
    <>
      {isFinalStep ? (
        <Button type="button" loading={isPending} round onClick={onDeploy}>
          Deploy
        </Button>
      ) : (
        <Button type="button" round onClick={onNext}>
          Continue
        </Button>
      )}
      {isFirstStep ? (
        <Button variant="outline" round onClick={handleCancel}>
          Cancel
        </Button>
      ) : (
        <Button variant="outline" round onClick={onBack}>
          Back
        </Button>
      )}
    </>
  );
};

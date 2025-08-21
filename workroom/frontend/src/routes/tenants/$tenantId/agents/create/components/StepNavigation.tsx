import { FC } from 'react';
import { Button } from '@sema4ai/components';

type Props = {
  isFinalStep: boolean;
  isPending: boolean;
  isFirstStep: boolean;
  onBack: () => void;
};

export const StepNavigation: FC<Props> = ({ isFinalStep, isPending, isFirstStep, onBack }) => {
  const handleCancel = () => {
    console.log('Cancel clicked');
  };

  return (
    <>
      <Button type="submit" loading={isPending} round>
        {isFinalStep ? 'Deploy' : 'Continue'}
      </Button>
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

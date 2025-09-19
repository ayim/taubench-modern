import { FC, useState } from 'react';
import { Button, Dialog } from '@sema4ai/components';
import { useNavigate, useParams } from '@tanstack/react-router';

type Props = {
  isFinalStep: boolean;
  isPending: boolean;
  isFirstStep: boolean;
  onBack: () => void;
  onNext: () => void;
  onDeploy: () => void;
};

export const StepNavigation: FC<Props> = ({ isFinalStep, isPending, isFirstStep, onBack, onNext, onDeploy }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/deploy' });
  const navigate = useNavigate();
  const [isCancel, setIsCancel] = useState(false);
  const handleCancel = () => {
    navigate({ to: '/tenants/$tenantId/home', params: { tenantId } });
  };

  return (
    <>
      {isFinalStep || isFirstStep ? (
        <Button type="button" loading={isPending} round onClick={isFinalStep ? onDeploy : onNext}>
          Deploy
        </Button>
      ) : (
        <Button type="button" round onClick={onNext}>
          Continue
        </Button>
      )}
      {isFirstStep ? (
        <Button variant="outline" round onClick={() => setIsCancel(true)}>
          Cancel
        </Button>
      ) : (
        <Button variant="outline" round onClick={onBack}>
          Back
        </Button>
      )}
      {isCancel && (
        <Dialog open onClose={() => setIsCancel(false)}>
          <Dialog.Header>
            <Dialog.Header.Title title="Are you sure?" />
          </Dialog.Header>
          <Dialog.Content> This will discard all changes and return to the home page. </Dialog.Content>
          <Dialog.Actions>
            <Button variant="primary" round onClick={handleCancel}>
              Confirm
            </Button>
            <Button variant="outline" round onClick={() => setIsCancel(false)}>
              Cancel
            </Button>
          </Dialog.Actions>
        </Dialog>
      )}
    </>
  );
};

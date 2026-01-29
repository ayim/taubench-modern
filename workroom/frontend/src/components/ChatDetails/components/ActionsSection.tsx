import { Typography } from '@sema4ai/components';
import { IconActions } from '@sema4ai/icons';
import { AgentCard } from '@sema4ai/layouts';
import { ActionPackage } from '../index';

export const ActionsSection = ({ actionPackages }: { actionPackages: ActionPackage[] }) => {
  return (
    <>
      <Typography variant="body-medium" fontWeight="bold">
        Actions
      </Typography>
      <AgentCard.ActionPackageList>
        {actionPackages.map((actionPackage) => (
          <AgentCard.ActionPackageList.Item
            key={`${actionPackage.name}-${actionPackage.version}`}
            name={actionPackage.name}
            description={null}
            actions={actionPackage.actions}
            illustration={<IconActions />}
            version={actionPackage.version}
          />
        ))}
      </AgentCard.ActionPackageList>
    </>
  );
};

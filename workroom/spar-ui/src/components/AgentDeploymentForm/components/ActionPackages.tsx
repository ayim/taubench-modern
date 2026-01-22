/* eslint-disable jsx-a11y/anchor-is-valid */
import { FC, useRef, useState } from 'react';
import { IconActionBadge, IconActions } from '@sema4ai/icons';
import { Badge, Box, Link, Transition, Typography } from '@sema4ai/components';

import { InputControlled } from '../../../common/form/InputControlled';
import { AgentDeploymentFormSection } from '../context';
import { AgentPackageInspectionResponse } from '../../../queries';
import { parseWhitelist, getUniqueSecretsMap } from '../../../utils/actionPackages';

type ActionPackage = NonNullable<NonNullable<AgentPackageInspectionResponse>['action_packages']>[number];

const ActionPackageItem: FC<{ actionPackage: ActionPackage }> = ({ actionPackage }) => {
  const [detailsOpen, setDetailsOpen] = useState<boolean>(false);
  const detailsRef = useRef<HTMLDivElement>(null);

  const icon = actionPackage.icon ? (
    <img src={actionPackage.icon} alt={`Icon of ${actionPackage.name}`} width={24} height={24} />
  ) : (
    <IconActions size={24} />
  );

  const whitelist = parseWhitelist(actionPackage.whitelist);
  const secretsMap = getUniqueSecretsMap(actionPackage, whitelist);

  return (
    <Box display="flex" gap="$18">
      {icon}
      <Box flex="1">
        <Typography variant="body-large" fontWeight="medium" mb="$4">
          {actionPackage.name}
        </Typography>
        <Link as="button" type="button" variant="dashed" onClick={() => setDetailsOpen(!detailsOpen)}>
          Show Details
        </Link>
        <div ref={detailsRef}>
          <Transition.Collapse in={detailsOpen} nodeRef={detailsRef}>
            {actionPackage.actions && actionPackage.actions.length > 0 && (
              <Box pt="$16">
                <Typography mb="$4">{actionPackage.description}</Typography>
                <Typography color="content.subtle" mb="$16">
                  Version {actionPackage.version}
                </Typography>
                <Typography variant="body-medium" mb="$8" fontWeight="medium">
                  Actions
                </Typography>
                <Box display="flex" gap="$4" flexWrap="wrap">
                  {actionPackage.actions.map((action) => (
                    <Badge
                      icon={IconActionBadge}
                      iconColor="content.subtle.light"
                      key={action.name}
                      variant="secondary"
                      label={action.name}
                    />
                  ))}
                </Box>
              </Box>
            )}
          </Transition.Collapse>
        </div>
        {secretsMap.size > 0 && (
          <Box display="grid" pt="$16" gap="$12">
            {Array.from(secretsMap.entries()).map(([secretName, secret]) => (
              <InputControlled
                label={secretName}
                fieldName={`agentPackageSecrets.${secretName}`}
                aria-label={`Secret value for ${secretName}`}
                placeholder={`Enter ${secretName}`}
                description={secret.description}
                type="password"
              />
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
};

export const ActionPackages: AgentDeploymentFormSection = ({ agentTemplate: { action_packages: actionPackages } }) => {
  if (!actionPackages) {
    return null;
  }

  return actionPackages.map((actionPackage) => (
    <ActionPackageItem key={actionPackage.name} actionPackage={actionPackage} />
  ));
};

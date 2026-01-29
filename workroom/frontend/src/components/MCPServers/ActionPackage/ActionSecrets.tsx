import type { FC } from 'react';
import { Box } from '@sema4ai/components';

import { AgentPackageInspectionResponse } from '~/queries/agentPackageInspection';
import { InputControlled } from '~/components/form/InputControlled';
import { parseWhitelist, getUniqueSecretsMap } from '../../../utils/actionPackages';

export const ActionSecrets: FC<{
  actionPackage: NonNullable<NonNullable<AgentPackageInspectionResponse>['action_packages']>[number];
}> = ({ actionPackage }) => {
  if (!actionPackage.secrets) {
    return null;
  }

  const whitelist = parseWhitelist(actionPackage.whitelist);
  const uniqueSecretsMap = getUniqueSecretsMap(actionPackage, whitelist);

  if (uniqueSecretsMap.size === 0) {
    return null;
  }

  return (
    <Box>
      <Box mb="$16">
        <Box fontSize="$14" fontWeight="medium" mb="$8">
          Configure secrets
        </Box>
        <Box fontSize="$14" color="content.subtle">
          Complete configuration to interact with related accounts and actions.
        </Box>
      </Box>
      <Box display="grid" gap="$16">
        {Array.from(uniqueSecretsMap.entries()).map(([secretName, secretInfo]) => (
          <Box key={secretName} display="flex" flexDirection={['column', 'column', 'row']} gap={['$8', '$8', '$24']}>
            <Box flexBasis={['1', '1', 240]}>
              <Box fontWeight="medium" mb="$4">
                {secretName}
              </Box>
              <Box fontSize="$14" color="content.subtle">
                {secretInfo.description || `Secret value for ${secretName}`}
              </Box>
            </Box>
            <Box flex="1">
              <InputControlled
                fieldName={`agentPackageSecrets.${secretName}`}
                aria-label={`Secret value for ${secretName}`}
                placeholder={`Enter ${secretName}`}
                type="password"
              />
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

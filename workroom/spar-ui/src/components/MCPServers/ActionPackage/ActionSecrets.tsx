import type { FC } from 'react';
import { Box, Input } from '@sema4ai/components';
import { useFormContext, Controller } from 'react-hook-form';

import { parseWhitelist, getUniqueSecretsMap, AgentPackageActionPackageMetadata } from './actionPackageUtils';

export const ActionSecrets: FC<{
  actionPackage: AgentPackageActionPackageMetadata;
}> = ({ actionPackage }) => {
  const { control, formState } = useFormContext();

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
        {Array.from(uniqueSecretsMap.entries()).map(([secretName, secretInfo]) => {
          const errors = formState.errors?.agentPackageSecrets as Record<string, { message?: string }> | undefined;
          const error = errors?.[secretName];

          return (
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
                <Controller
                  control={control}
                  name={`agentPackageSecrets.${secretName}`}
                  render={({ field }) => (
                    <Input
                      aria-labelledby={`secret-${secretName}-label`}
                      placeholder={`Enter ${secretName}`}
                      type="password"
                      error={error?.message}
                      {...field}
                    />
                  )}
                />
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

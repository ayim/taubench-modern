import type { FC } from 'react';
import { Box, Input } from '@sema4ai/components';
import { useFormContext, Controller } from 'react-hook-form';

import { parseWhitelist, getUniqueSecretsMap } from './actionPackageUtils';
import { components } from '@sema4ai/agent-server-interface';

export const ActionSecrets: FC<{
  actionPackage: components['schemas']['AgentPackageActionPackageMetadata'];
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
        <Box style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>Configure secrets</Box>
        <Box style={{ fontSize: '0.875rem', opacity: 0.7 }}>
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
                <Box style={{ fontFamily: 'monospace', fontWeight: 500, marginBottom: '0.25rem' }}>{secretName}</Box>
                <Box style={{ fontSize: '0.875rem', opacity: 0.7 }}>
                  {secretInfo.description || `Secret value for ${secretName}`}
                </Box>
              </Box>
              <Box flex="1">
                <Controller
                  control={control}
                  name={`agentPackageSecrets.${secretName}` as const}
                  render={({ field }) => (
                    <Input
                      aria-labelledby={`secret-${secretName}-label`}
                      placeholder={`Enter ${secretName}`}
                      type="password"
                      error={error?.message as string | undefined}
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

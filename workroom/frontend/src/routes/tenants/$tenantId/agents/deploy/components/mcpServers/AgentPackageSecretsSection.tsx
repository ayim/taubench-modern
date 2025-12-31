import { FC, useMemo } from 'react';
import { Box, Typography, Input } from '@sema4ai/components';
import { Controller, useFormContext } from 'react-hook-form';
import { AgentCard } from '@sema4ai/layouts';
import { IconActions, IconStatusCompleted } from '@sema4ai/icons';
import { AgentPackageInspectionResponse } from '@sema4ai/spar-ui/queries';
import { parseWhitelist, getUniqueSecretsMap } from '@sema4ai/spar-ui';

export const AgentPackageSecretsSection: FC<{
  agentTemplate: NonNullable<AgentPackageInspectionResponse>;
}> = ({ agentTemplate }) => {
  const { control, formState } = useFormContext();

  const packagesWithSecretsInfo = useMemo(() => {
    const actionPackages = agentTemplate.action_packages ?? [];
    return actionPackages.map((pkg) => {
      const whitelist = parseWhitelist(pkg.whitelist);
      const secretsMap = getUniqueSecretsMap(pkg, whitelist);
      return { pkg, secretsMap, hasSecrets: secretsMap.size > 0 };
    });
  }, [agentTemplate.action_packages]);

  if (packagesWithSecretsInfo.length === 0) {
    return null;
  }

  return (
    <Box display="flex" flexDirection="column" gap="$16" mb="$24">
      {packagesWithSecretsInfo.map(({ pkg, secretsMap, hasSecrets }) => (
        <Box
          key={`${pkg.name}-${pkg.version}`}
          borderColor="border.subtle"
          borderRadius="$8"
          borderWidth="1px"
          paddingX="$8"
        >
          <AgentCard.ActionPackageList>
            <AgentCard.ActionPackageList.Item
              illustration={
                pkg.icon ? (
                  <img src={pkg.icon} alt={`Icon of ${pkg.name}`} width={24} height={24} />
                ) : (
                  <IconActions size="m" />
                )
              }
              name={pkg.name}
              description={pkg.description}
              version={pkg.version}
              actions={pkg.actions ?? []}
              queries={[]}
              mcpTools={[]}
              statusIcon={hasSecrets ? undefined : <IconStatusCompleted size="s" />}
            />
          </AgentCard.ActionPackageList>

          {hasSecrets && (
            <Box p="$16" borderTopWidth="1px">
              <Typography fontSize="$14" fontWeight="medium" mb="$12">
                Configure secrets
              </Typography>
              <Box display="grid" gap="$12">
                {Array.from(secretsMap.entries()).map(([secretName, secretInfo]) => {
                  const fieldPath = `agentPackageSecrets.${secretName}` as const;
                  const errors = formState.errors?.agentPackageSecrets as
                    | Record<string, { message?: string }>
                    | undefined;
                  const error = errors?.[secretName];

                  return (
                    <Box
                      key={secretName}
                      display="flex"
                      flexDirection={['column', 'column', 'row']}
                      gap={['$8', '$8', '$16']}
                      alignItems={['flex-start', 'flex-start', 'center']}
                    >
                      <Box flexBasis={['auto', 'auto', 180]} flexShrink={0}>
                        <Typography fontWeight="medium" fontSize="$14">
                          {secretName}
                        </Typography>
                        {secretInfo.description && (
                          <Typography fontSize="$12" color="content.subtle">
                            {secretInfo.description}
                          </Typography>
                        )}
                      </Box>
                      <Box flex="1" width="100%">
                        <Controller
                          control={control}
                          name={fieldPath}
                          render={({ field }) => (
                            <Input
                              aria-label={`Secret value for ${secretName}`}
                              placeholder={`Enter ${secretName}`}
                              type="password"
                              error={error?.message}
                              {...field}
                              value={field.value ?? ''}
                            />
                          )}
                        />
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            </Box>
          )}
        </Box>
      ))}
    </Box>
  );
};

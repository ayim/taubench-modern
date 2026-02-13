import { useMemo } from 'react';
import { Box, Select, Typography } from '@sema4ai/components';

import { useUserRole, UserRole } from '~/hooks/useUserRole';
import { getLLMProviderIcon } from '~/components/helpers';
import { usePlatformsQuery } from '~/queries/platforms';
import { useAgentDetailsContext } from './context';

export const LLM = () => {
  const { data: platforms, isLoading: isPlatformsLoading } = usePlatformsQuery({});
  const { agent, updateAgent } = useAgentDetailsContext();
  const hasAdminRole = useUserRole(UserRole.Admin);

  const { selectItems, activePlatform } = useMemo(() => {
    return {
      selectItems:
        platforms?.map((platform) => ({
          value: platform.platform_id,
          label: platform.name,
        })) || [],
      activePlatform: platforms?.find((platform) => platform.platform_id === agent.platform_params_ids?.[0]),
    };
  }, [platforms, agent]);

  const onPlatformChange = (value: string) => {
    if (value !== activePlatform?.platform_id) {
      updateAgent({ platform_params_ids: [value] });
    }
  };

  const PlatformIcon = activePlatform && getLLMProviderIcon(activePlatform?.kind);

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      {hasAdminRole ? (
        <Select
          iconLeft={PlatformIcon}
          label="Large Language Model"
          items={selectItems}
          disabled={isPlatformsLoading}
          value={activePlatform?.platform_id}
          onChange={onPlatformChange}
        />
      ) : (
        <>
          <Typography fontWeight="bold" mb="$4">
            Large Language Model
          </Typography>
          <Box display="flex" gap="$8" alignItems="center">
            {PlatformIcon && <PlatformIcon />}
            <Typography>{activePlatform?.name}</Typography>
          </Box>
        </>
      )}
    </Box>
  );
};

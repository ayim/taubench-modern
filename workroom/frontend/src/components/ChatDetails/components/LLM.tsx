/* eslint-disable camelcase */
import { useMemo } from 'react';
import { Box, Select } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { getLLMProviderIcon } from '~/components/helpers';
import { usePlatformsQuery } from '~/queries/platforms';
import { AgentDetailsSchema } from './context';

export const LLM = () => {
  const { data: platforms, isLoading: isPlatformsLoading } = usePlatformsQuery({});
  const { watch, setValue } = useFormContext<AgentDetailsSchema>();
  const { platform_params_ids } = watch();

  const { selectItems, activePlatform } = useMemo(() => {
    return {
      selectItems:
        platforms?.map((platform) => ({
          value: platform.platform_id,
          label: platform.name,
        })) || [],
      activePlatform: platforms?.find((platform) => platform.platform_id === platform_params_ids?.[0]),
    };
  }, [platforms, platform_params_ids]);

  const onPlatformChange = (value: string) => {
    setValue('platform_params_ids', [value], { shouldDirty: true });
  };

  const PlatformIcon = activePlatform && getLLMProviderIcon(activePlatform?.kind);

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Select
        iconLeft={PlatformIcon}
        label="Large Language Model"
        items={selectItems}
        disabled={isPlatformsLoading}
        value={activePlatform?.platform_id}
        onChange={onPlatformChange}
      />
    </Box>
  );
};

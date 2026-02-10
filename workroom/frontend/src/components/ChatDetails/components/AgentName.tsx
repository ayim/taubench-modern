import { useFormContext } from 'react-hook-form';
import { Box, Label } from '@sema4ai/components';
import { AgentIcon } from '@sema4ai/layouts';

import { InputControlled } from '~/components/form/InputControlled';
import { FeatureFlag, useFeatureFlag } from '~/hooks/useFeatureFlag';
import { AgentDetailsSchema } from './context';

export const AgentName = () => {
  const { enabled: canConfigureAgents } = useFeatureFlag(FeatureFlag.canConfigureAgents);
  const { watch } = useFormContext<AgentDetailsSchema>();
  const { name, mode } = watch();

  if (!canConfigureAgents) {
    return null;
  }

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Label>Icon & Name</Label>
      <Box display="flex" gap="$8">
        <AgentIcon mode={mode} identifier={name} />
        <Box flex="1">
          <InputControlled fieldName="name" aria-label="Agent Name" />
        </Box>
      </Box>
    </Box>
  );
};

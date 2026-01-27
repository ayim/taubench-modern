import { Box, Label, Typography } from '@sema4ai/components';
import { AgentIcon } from '@sema4ai/layouts';
import { useFormContext } from 'react-hook-form';

import { AgentDeploymentFormSchema, AgentDeploymentFormSection } from '../context';
import { InputControlled } from '../../../common/form/InputControlled';

export const AgentName: AgentDeploymentFormSection = () => {
  const { watch } = useFormContext<AgentDeploymentFormSchema>();
  const { name, mode } = watch();

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Label>Icon & Name</Label>
      <Box display="flex" gap="$8">
        <AgentIcon mode={mode} identifier={name} />
        <Box flex="1">
          <InputControlled autoFocus fieldName="name" aria-label="Agent Name" />
        </Box>
      </Box>
      <Typography color="content.subtle.light">Give your agent a short, descriptive name.</Typography>
    </Box>
  );
};

import { useEffect, useRef } from 'react';
import { Box, Label, Typography } from '@sema4ai/components';
import { AgentIcon } from '@sema4ai/layouts';
import { InputControlled } from '~/components/form/InputControlled';
import { useFormContext } from 'react-hook-form';

import { CreateAgentFormSchema } from './context';

export const AgentName = () => {
  const { watch } = useFormContext<CreateAgentFormSchema>();
  const { name, mode } = watch();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.select();
    }
  }, []);

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Label>Icon & Name</Label>
      <Box display="flex" gap="$8">
        <AgentIcon mode={mode} identifier={name} />
        <Box flex="1">
          <InputControlled ref={inputRef} fieldName="name" aria-label="Agent Name" />
        </Box>
      </Box>
      <Typography color="content.subtle.light">Give your agent a short, descriptive name.</Typography>
    </Box>
  );
};

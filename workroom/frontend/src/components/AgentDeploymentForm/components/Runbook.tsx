import { useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Button, Typography } from '@sema4ai/components';
import { IconEdit } from '@sema4ai/icons';

import { RunbookDialog } from '~/components/RunbookEditor';

import { AgentDeploymentFormSchema } from '../context';

export const Runbook = () => {
  const [isRunbookDialogOpen, setIsRunbookDialogOpen] = useState(false);
  const { watch, setValue } = useFormContext<AgentDeploymentFormSchema>();

  const runbook = watch('runbook');

  if (!runbook) {
    return null;
  }

  const onCloseRunbookDialog = (value?: string) => {
    setIsRunbookDialogOpen(false);

    if (value) {
      setValue('runbook', value);
    }
  };

  return (
    <Box>
      <Typography fontWeight="medium">Runbook</Typography>
      <Typography color="content.subtle">
        provide instructions in natural language, which define how the agent should perform its work
      </Typography>
      <Box display="flex" gap="$8" py="$8">
        <Button icon={IconEdit} variant="secondary" onClick={() => setIsRunbookDialogOpen(true)} round>
          Edit Runbook
        </Button>
      </Box>
      {isRunbookDialogOpen ? <RunbookDialog onClose={onCloseRunbookDialog} value={runbook} /> : null}
    </Box>
  );
};

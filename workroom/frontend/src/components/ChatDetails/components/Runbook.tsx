import { useEffect, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Button, Label, Progress } from '@sema4ai/components';
import { IconShare } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';

import { useAgentDetailsQuery } from '~/queries/agents';
import { RunbookDialog } from '~/components/RunbookEditor';
import { FeatureFlag, useFeatureFlag } from '~/hooks/useFeatureFlag';
import { AgentDetailsSchema } from './context';

export const Runbook = () => {
  const { agentId = '' } = useParams({ strict: false });
  const [isRunbookDialogOpen, setIsRunbookDialogOpen] = useState(false);
  const { enabled: canConfigureAgents } = useFeatureFlag(FeatureFlag.canConfigureAgents);
  const { setValue } = useFormContext<AgentDetailsSchema>();
  const { data, isLoading } = useAgentDetailsQuery({ agentId });
  const [runbook, setRunbook] = useState<string | undefined>('');

  useEffect(() => {
    if (data?.runbook) {
      setRunbook(data.runbook);
    }
  }, [data]);

  const onOpenRunbookDialog = () => {
    setIsRunbookDialogOpen(true);
  };

  const onCloseRunbookDialog = (value?: string) => {
    setIsRunbookDialogOpen(false);

    if (value) {
      setRunbook(value);
      setValue('runbook', value, { shouldDirty: true });
    }
  };

  if (isLoading && isRunbookDialogOpen) {
    return <Progress variant="page" />;
  }

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Label>Runbook</Label>
      <Box>
        <Button disabled={isLoading} iconAfter={IconShare} variant="outline" onClick={onOpenRunbookDialog} round>
          {canConfigureAgents ? 'Edit Runbook' : 'View Runbook'}
        </Button>
      </Box>
      {isRunbookDialogOpen && runbook && (
        <RunbookDialog readOnly={!canConfigureAgents} onClose={onCloseRunbookDialog} value={runbook} />
      )}
    </Box>
  );
};
